import json
import logging
from datetime import timezone

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from webhook.amocrm_client import AmoCRMClient
from webhook.models import WebhookLog

logger = logging.getLogger(__name__)


def verify_radario_webhook(payload):
    """Проверка вебхука от Радарио (без секретного ключа)"""
    # Проверяем наличие поля 'model'
    if 'model' not in payload:
        logger.error(f"No 'model' field in payload: {payload.keys()}")
        return False

    model = payload['model']

    # Проверяем обязательные поля внутри model
    required_fields = ['Id', 'Email', 'Status', 'Event']

    # Проверяем наличие полей (учитываем разный регистр)
    for field in required_fields:
        if field not in model and field.lower() not in model:
            logger.error(f"Missing required field '{field}' in model. Available fields: {list(model.keys())}")
            return False

    return True


def extract_customer_info(webhook_data):
    """Извлечение информации о покупателе из вебхука Радарио"""
    try:
        # Данные находятся внутри 'model'
        model = webhook_data.get('model', {})

        email = model.get('Email', '') or model.get('email', '')
        phone = model.get('User', {}).get('Phone', '') or model.get('user', {}).get('phone', '')

        # Имя из билетов или пользователя
        name = "Покупатель билета"
        tickets = model.get('Tickets', []) or model.get('tickets', [])

        if tickets and tickets[0].get('OwnerName'):
            name = tickets[0]['OwnerName']
        elif tickets and tickets[0].get('participantName'):
            name = tickets[0]['participantName']
        elif model.get('User') and model['User'].get('Name'):
            name = model['User']['Name']
        elif model.get('user') and model['user'].get('name'):
            name = model['user']['name']

        # Данные о возврате
        # Данные о возврате
        refund_details = model.get('RefundDetails', {}) or model.get('refundDetails', {})
        refund_date = refund_details.get('RefundDate') if refund_details else None

        # Получаем статусы
        status = model.get('Status') or model.get('status')
        payment_system_status = model.get('PaymentSystemStatus') or model.get('paymentSystemStatus')

        # Для возвратов: если статус Refunded, но нет refund_date,
        # используем updateDate или текущее время
        if (status == 'Refunded' or payment_system_status == 'Refund') and not refund_date:
            refund_date = model.get('UpdateDate') or model.get('updateDate')
            if not refund_date:
                # Если нет даты возврата, используем текущее время
                from datetime import datetime
                refund_date = datetime.now().isoformat() + 'Z'

        return {
            'email': email,
            'name': name,
            'phone': phone,
            'order_id': model.get('Id') or model.get('id'),
            'status': model.get('Status') or model.get('status'),
            'payment_system_status': model.get('PaymentSystemStatus') or model.get('paymentSystemStatus'),
            'payment_system_status_description': model.get('PaymentSystemStatusDescription') or model.get('paymentSystemStatusDescription', ''),
            'amount': float(model.get('Amount', 0) or model.get('amount', 0)),
            'host_profit': float(model.get('HostProfit', 0) or model.get('hostProfit', 0)),
            'creation_date': model.get('CreationDate') or model.get('creationDate', ''),
            'payment_date': model.get('PaymentDate') or model.get('paymentDate', ''),
            'update_date': model.get('UpdateDate') or model.get('updateDate', ''),
            'event_title': model.get('Event', {}).get('Title', '') or model.get('event', {}).get('title', ''),
            'event_date': model.get('Event', {}).get('BeginDate', '') or model.get('event', {}).get('beginDate', ''),
            'tickets_count': len(tickets),
            'tickets': tickets,
            'refund_date': refund_date,  # ← Должно быть заполнено
            'refund_details': refund_details,
            'payment_type': model.get('PaymentType') or model.get('paymentType', ''),
            'promocode': model.get('Promocode') or model.get('promocode', ''),
            'distribution_type': model.get('DistributionType') or model.get('distributionType', ''),
            'currency': model.get('Currency') or model.get('currency', 'RUB'),
            'utm_data': model.get('UtmData') or model.get('utmData', {}),
            'custom_data': model.get('CustomData') or model.get('customData', ''),
            'source': 'Radario'
        }
    except Exception as e:
        logger.error(f"Error extracting customer info: {e}")
        return {
            'email': model.get('Email', '') or model.get('email', ''),
            'name': 'Покупатель билета',
            'phone': '',
            'order_id': model.get('Id') or model.get('id'),
            'status': model.get('Status') or model.get('status'),
            'amount': float(model.get('Amount', 0) or model.get('amount', 0))
        }


def create_lead_name(event_data, order_id):
    """Создание названия для сделки в amoCRM"""
    event_title = event_data.get('Title') or event_data.get('title', 'Мероприятие')
    event_date = (event_data.get('BeginDate') or event_data.get('beginDate', '')).split('T')[0]

    if event_date:
        return f"Билет на {event_title} ({event_date}) - Заказ #{order_id}"
    else:
        return f"Билет на {event_title} - Заказ #{order_id}"


def should_process_order(webhook_data):
    """Проверяем, нужно ли обрабатывать заказ"""
    status = webhook_data.get('Status')
    payment_status = webhook_data.get('PaymentSystemStatus')

    # Обрабатываем ВСЕ заказы (Paid, Refunded, Cancelled и т.д.)
    # чтобы заполнять информацию в amoCRM
    return True  # Всегда обрабатываем


