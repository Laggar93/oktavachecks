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
    # Так как Радарио не использует секретный ключ, просто проверяем наличие обязательных полей
    required_fields = ['Id', 'Email', 'Status', 'Event']
    if not all(field in payload for field in required_fields):
        return False
    return True


def extract_customer_info(webhook_data):
    """Извлечение информации о покупателе из вебхука Радарио по новой модели"""
    try:
        email = webhook_data.get('Email', '')
        phone = webhook_data.get('User', {}).get('Phone', '')

        # Имя из билетов или пользователя
        name = "Покупатель билета"
        tickets = webhook_data.get('Tickets', [])
        if tickets and tickets[0].get('OwnerName'):
            name = tickets[0]['OwnerName']
        elif webhook_data.get('User') and webhook_data['User'].get('Name'):
            name = webhook_data['User']['Name']

        # Данные о возврате
        refund_details = webhook_data.get('RefundDetails', {})
        refund_date = refund_details.get('RefundDate') if refund_details else None

        return {
            'email': email,
            'name': name,
            'phone': phone,
            'order_id': webhook_data.get('Id'),
            'status': webhook_data.get('Status'),
            'payment_system_status': webhook_data.get('PaymentSystemStatus'),
            'payment_system_status_description': webhook_data.get('PaymentSystemStatusDescription', ''),
            'amount': float(webhook_data.get('Amount', 0)),
            'host_profit': float(webhook_data.get('HostProfit', 0)),
            'creation_date': webhook_data.get('CreationDate', ''),
            'payment_date': webhook_data.get('PaymentDate', ''),
            'update_date': webhook_data.get('UpdateDate', ''),
            'event_title': webhook_data.get('Event', {}).get('Title', ''),
            'event_date': webhook_data.get('Event', {}).get('BeginDate', ''),
            'tickets_count': len(tickets),
            'tickets': tickets,
            'refund_date': refund_date,
            'refund_details': refund_details,
            'payment_type': webhook_data.get('PaymentType', ''),
            'promocode': webhook_data.get('Promocode', ''),
            'distribution_type': webhook_data.get('DistributionType', ''),
            'currency': webhook_data.get('Currency', 'RUB'),
            'utm_data': webhook_data.get('UtmData', {}),
            'custom_data': webhook_data.get('CustomData', ''),
            'source': 'Radario'
        }
    except Exception as e:
        logger.error(f"Error extracting customer info: {e}")
        return {
            'email': webhook_data.get('Email', ''),
            'name': 'Покупатель билета',
            'phone': '',
            'order_id': webhook_data.get('Id'),
            'status': webhook_data.get('Status'),
            'amount': float(webhook_data.get('Amount', 0))
        }


def create_lead_name(event_data, order_id):
    """Создание названия для сделки в amoCRM"""
    event_title = event_data.get('Title', 'Мероприятие')
    event_date = event_data.get('BeginDate', '').split('T')[0]  # Берем только дату

    if event_date:
        return f"Билет на {event_title} ({event_date}) - Заказ #{order_id}"
    else:
        return f"Билет на {event_title} - Заказ #{order_id}"


def should_process_order(webhook_data):
    """Проверяем, нужно ли обрабатывать заказ"""
    status = webhook_data.get('Status')
    payment_status = webhook_data.get('PaymentSystemStatus')

    # Обрабатываем только оплаченные заказы
    return (status == 'Paid' and payment_status == 'Paid')


