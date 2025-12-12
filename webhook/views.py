import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from .models import WebhookLog
from .amocrm_client import AmoCRMClient
from .utils import verify_radario_webhook, extract_customer_info, create_lead_name, should_process_order

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def radario_webhook(request):

    raw_body = request.body.decode('utf-8')
    logger.info(f"Received Radario webhook: {raw_body[:500]}...")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON: {e}")
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    webhook_log = WebhookLog.objects.create(payload=payload)

    try:
        if not verify_radario_webhook(payload):
            webhook_log.status = 'error'
            webhook_log.error_message = 'Missing required fields'
            webhook_log.save()
            return JsonResponse({'status': 'error', 'message': 'Missing required fields'}, status=400)

        customer_info = extract_customer_info(payload)
        if not customer_info['email']:
            webhook_log.status = 'error'
            webhook_log.error_message = 'No email provided'
            webhook_log.save()
            return JsonResponse({'status': 'error', 'message': 'No email provided'}, status=400)

        amocrm = AmoCRMClient()

        contact = amocrm.find_contact_by_email(customer_info['email'])

        if contact:
            contact_id = contact['id']
            logger.info(f"Found existing contact: {contact_id}")
        else:
            contact = amocrm.create_contact(
                email=customer_info['email'],
                name=customer_info['name'],
                phone=customer_info['phone']
            )
            contact_id = contact['id']
            logger.info(f"Created new contact: {contact_id}")

        model = payload.get('model', {})
        event_data = model.get('Event', {}) or model.get('event', {})

        status = customer_info.get('status')
        payment_status = customer_info.get('payment_system_status')

        existing_lead = amocrm.find_lead_by_order_id(customer_info['order_id'])

        if existing_lead:
            lead_id = existing_lead['id']

            if status == 'Refunded' or payment_status == 'Refund':
                logger.info(f"Processing refund for existing lead: {lead_id}")
                amocrm.update_lead_for_refund(lead_id, customer_info)
            else:
                logger.info(f"Updating existing lead: {lead_id}")

                if status == 'Paid' and payment_status == 'Paid':
                    amocrm.update_lead(lead_id, customer_info, status_id=77419554)
                else:
                    amocrm.update_lead(lead_id, customer_info)
        else:
            lead_name = create_lead_name(event_data, customer_info['order_id'])

            if status == 'Refunded' or payment_status == 'Refund':
                logger.info(f"Creating new lead for refund: {customer_info['order_id']}")
                lead = amocrm.create_lead_with_custom_fields(
                    contact_id=contact_id,
                    customer_info=customer_info
                )
            else:
                logger.info(f"Creating new lead: {customer_info['order_id']}")
                lead = amocrm.create_lead_with_custom_fields(
                    contact_id=contact_id,
                    customer_info=customer_info
                )

            lead_id = lead['id']

        webhook_log.status = 'success'
        webhook_log.amocrm_contact_id = contact_id
        webhook_log.amocrm_lead_id = lead_id
        webhook_log.processed_at = timezone.now()
        webhook_log.save()

        return JsonResponse({
            'status': 'success',
            'contact_id': contact_id,
            'lead_id': lead_id
        })

    except Exception as e:
        logger.error(f"Webhook processing error: {e}", exc_info=True)
        webhook_log.status = 'error'
        webhook_log.error_message = str(e)
        webhook_log.save()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@require_http_methods(["GET"])
def health_check(request):
    return JsonResponse({'status': 'ok', 'service': 'oktavachecks'})