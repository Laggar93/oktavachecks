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
    """Обработчик вебхуков от Радарио"""

    raw_body = request.body.decode('utf-8')
    logger.info(f"Received Radario webhook: {raw_body[:500]}...")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON: {e}")
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    # Создаем запись в логе
    webhook_log = WebhookLog.objects.create(payload=payload)

    try:
        # Проверяем обязательные поля
        if not verify_radario_webhook(payload):
            webhook_log.status = 'error'
            webhook_log.error_message = 'Missing required fields'
            webhook_log.save()
            return JsonResponse({'status': 'error', 'message': 'Missing required fields'}, status=400)

        # Извлекаем информацию о покупателе
        customer_info = extract_customer_info(payload)
        if not customer_info['email']:
            webhook_log.status = 'error'
            webhook_log.error_message = 'No email provided'
            webhook_log.save()
            return JsonResponse({'status': 'error', 'message': 'No email provided'}, status=400)

        # Работа с amoCRM
        amocrm = AmoCRMClient()

        # 1. Ищем существующий контакт
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

        # 2. Создаем сделку
        # Получаем event из model
        model = payload.get('model', {})
        event_data = model.get('Event', {}) or model.get('event', {})

        lead_name = create_lead_name(event_data, customer_info['order_id'])

        lead = amocrm.create_lead(
            contact_id=contact_id,
            lead_name=lead_name,
            amount=customer_info['amount']
        )
        lead_id = lead['id']
        logger.info(f"Created lead: {lead_id}")

        # Обновляем лог
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
    """Проверка работоспособности сервиса"""
    return JsonResponse({'status': 'ok', 'service': 'oktavachecks'})