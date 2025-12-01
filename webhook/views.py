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
    """Обработчик вебхуков от Радарио - полная версия по ТЗ"""

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

        # 1. Ищем существующий контакт по email или телефону
        contact = None
        if customer_info['email']:
            contact = amocrm.find_contact_by_email(customer_info['email'])

        # Если не нашли по email, ищем по телефону (если нужно)
        if not contact and customer_info['phone']:
            contact = amocrm.find_contact_by_phone(customer_info['phone'])

        if contact:
            # Контакт существует
            contact_id = contact['id']
            logger.info(f"Found existing contact: {contact_id}")
            # Можно обновить контакт если нужно
        else:
            # Создаем новый контакт
            contact = amocrm.create_contact(
                email=customer_info['email'],
                name=customer_info['name'],
                phone=customer_info['phone']
            )
            contact_id = contact['id']
            logger.info(f"Created new contact: {contact_id}")

        # 2. Ищем существующую сделку по номеру заказа
        order_id = customer_info['order_id']
        existing_lead = amocrm.find_lead_by_order_id(order_id)

        if existing_lead:
            # Сделка существует - ОБНОВЛЯЕМ
            logger.info(f"Found existing lead: {existing_lead['id']}")

            # Проверяем статус на возврат
            is_refund = (customer_info['status'] == 'Refund' or
                         customer_info['payment_system_status'] == 'Refund')

            if is_refund:
                # Обработка возврата
                lead = amocrm.update_lead_for_refund(
                    lead_id=existing_lead['id'],
                    customer_info=customer_info
                )
                logger.info(f"Updated lead for refund: {existing_lead['id']}")
            else:
                # Обновление других данных
                lead = amocrm.update_lead(
                    lead_id=existing_lead['id'],
                    customer_info=customer_info
                )
                logger.info(f"Updated existing lead: {existing_lead['id']}")

            lead_id = existing_lead['id']
        else:
            # Создаем новую сделку
            logger.info(f"Creating new lead for order: {order_id}")
            lead = amocrm.create_lead_with_custom_fields(
                contact_id=contact_id,
                customer_info=customer_info
            )
            lead_id = lead['id']
            logger.info(f"Created new lead: {lead_id}")

        # Обновляем лог
        webhook_log.status = 'success'
        webhook_log.amocrm_contact_id = contact_id
        webhook_log.amocrm_lead_id = lead_id
        webhook_log.processed_at = timezone.now()
        webhook_log.save()

        return JsonResponse({
            'status': 'success',
            'contact_id': contact_id,
            'lead_id': lead_id,
            'action': 'updated' if existing_lead else 'created'
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