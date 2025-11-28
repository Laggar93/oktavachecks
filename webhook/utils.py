import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def verify_radario_webhook(payload):
    """Проверка вебхука от Радарио (без секретного ключа)"""
    # Так как Радарио не использует секретный ключ, просто проверяем наличие обязательных полей
    required_fields = ['Id', 'Email', 'Status', 'Event']
    if not all(field in payload for field in required_fields):
        return False
    return True


def extract_customer_info(webhook_data):
    """Извлечение информации о покупателе из вебхука Радарио"""
    try:
        email = webhook_data.get('Email', '')

        # Извлекаем имя из билетов или пользователя
        name = "Покупатель билета"  # значение по умолчанию

        # Пробуем получить имя из первого билета
        tickets = webhook_data.get('Tickets', [])
        if tickets and tickets[0].get('OwnerName'):
            name = tickets[0]['OwnerName']
        # Или из данных пользователя
        elif webhook_data.get('User') and webhook_data['User'].get('Name'):
            name = webhook_data['User']['Name']

        # Извлекаем телефон
        phone = ''
        if webhook_data.get('User') and webhook_data['User'].get('Phone'):
            phone = webhook_data['User']['Phone']

        return {
            'email': email,
            'name': name,
            'phone': phone
        }
    except Exception as e:
        logger.error(f"Error extracting customer info: {e}")
        return {
            'email': webhook_data.get('Email', ''),
            'name': 'Покупатель билета',
            'phone': ''
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