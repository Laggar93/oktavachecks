import hashlib
import hmac
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def verify_radario_webhook(payload, received_checksum):
    """Проверка подлинности вебхука от Радарио"""
    if not settings.RADARIO_WEBHOOK_SECRET:
        logger.warning("RADARIO_WEBHOOK_SECRET not set, skipping verification")
        return True

    # Создаем ожидаемую checksum
    message = f"{payload['notification']['salt']}{payload['notification']['timestamp']}"
    expected_checksum = hmac.new(
        settings.RADARIO_WEBHOOK_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_checksum, received_checksum)


def extract_customer_info(webhook_data):
    """Извлечение информации о покупателе из вебхука"""
    try:
        order_data = webhook_data['notification']['model']

        # В вебхуке Радарио может не быть явных полей покупателя
        # Используем email из заказа и создаем имя из доступных данных
        email = order_data.get('email', '')

        # Пытаемся извлечь имя из различных полей
        name = "Покупатель билета"  # значение по умолчанию

        # Если есть информация о билетах, можно попробовать извлечь оттуда
        tickets = order_data.get('tickets', [])
        if tickets and tickets[0].get('ownerName'):
            name = tickets[0]['ownerName']

        phone = order_data.get('phone', '')

        return {
            'email': email,
            'name': name,
            'phone': phone
        }
    except Exception as e:
        logger.error(f"Error extracting customer info: {e}")
        return {
            'email': '',
            'name': 'Покупатель билета',
            'phone': ''
        }


def create_lead_name(event_data, order_id):
    """Создание названия для сделки в amoCRM"""
    event_title = event_data.get('title', 'Мероприятие')
    event_date = event_data.get('beginDate', '').split('T')[0]  # Берем только дату

    if event_date:
        return f"Билет на {event_title} ({event_date}) - Заказ #{order_id}"
    else:
        return f"Билет на {event_title} - Заказ #{order_id}"