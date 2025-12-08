# webhook/test_full_cycle.py
import requests
import json
import time
from django.conf import settings

WEBHOOK_URL = "http://oktavachecks.twc1.net/webhook/radario/"


def extract_numbers_from_string(text):
    """Извлечение цифр из строки"""
    import re
    numbers = re.findall(r'\d+', str(text))
    return int(numbers[0]) if numbers else None


def send_webhook_test():
    """Тест отправки вебхука с преобразованием order_id"""

    # Тестовый order_id (как в реальных данных от Radario)
    order_id = "RAD-123456-789"  # Пример реального order_id

    # Извлекаем цифры для amoCRM
    order_number = extract_numbers_from_string(order_id)
    print(f"Order ID: {order_id}")
    print(f"Для amoCRM (поле 986103): {order_number}")

    data = {
        "model": {
            "Id": order_id,  # Оригинальный ID от Radario
            "Email": "test_webhook@example.com",
            "Status": "Paid",
            "PaymentSystemStatus": "Paid",
            "Amount": 2999.99,
            "Currency": "RUB",
            "CreationDate": "2024-01-15T10:30:00Z",
            "PaymentDate": "2024-01-15T10:35:00Z",
            "UpdateDate": "2024-01-15T10:35:00Z",
            "User": {
                "Name": "Тест Вебхук",
                "Phone": "+79161112233"
            },
            "Event": {
                "Id": "EVENT-TEST",
                "Title": "Тестовый мастер-класс",
                "BeginDate": "2024-01-20T15:00:00Z"
            },
            "Tickets": [
                {
                    "Id": "TICKET-TEST",
                    "OwnerName": "Тест Вебхук",
                    "Price": 2999.99,
                    "TicketType": "standard"
                }
            ]
        }
    }

    print(f"\n📤 Отправляю вебхук на {WEBHOOK_URL}")

    response = requests.post(
        WEBHOOK_URL,
        json=data,
        headers={'Content-Type': 'application/json'},
        timeout=30
    )

    print(f"Статус: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"✅ Успех!")
        print(f"Contact ID: {result.get('contact_id')}")
        print(f"Lead ID: {result.get('lead_id')}")

        # Проверяем в amoCRM
        print(f"\n🔍 Проверяем созданную сделку в amoCRM...")
        check_lead_in_amocrm(result.get('lead_id'), order_id, order_number)

    else:
        print(f"❌ Ошибка: {response.text}")

    return response


def check_lead_in_amocrm(lead_id, original_order_id, numeric_order_id):
    """Проверка созданной сделки в amoCRM"""
    import requests

    if not lead_id:
        return

    subdomain = settings.AMOCRM_SUBDOMAIN
    token = settings.AMOCRM_ACCESS_TOKEN
    url = f"https://{subdomain}.amocrm.ru/api/v4/leads/{lead_id}?with=custom_fields"

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            lead = response.json()
            print(f"✅ Сделка {lead_id} найдена в amoCRM")

            # Проверяем поле номера заказа
            if 'custom_fields_values' in lead:
                for field in lead['custom_fields_values']:
                    if field.get('field_id') == 986103:  # Номер заказа
                        field_value = field.get('values', [{}])[0].get('value')
                        print(f"   Поле 986103 (Номер заказа): {field_value}")
                        print(f"   Ожидалось: {numeric_order_id}")

                        if field_value == numeric_order_id:
                            print(f"   ✅ Числовое значение сохранено корректно")
                        else:
                            print(f"   ⚠️ Значение отличается")

            print(f"   Название: {lead.get('name')}")
            print(f"   Сумма: {lead.get('price') / 100 if lead.get('price') else 0} руб")

    except Exception as e:
        print(f"❌ Ошибка проверки сделки: {e}")


# Запуск теста
if __name__ == "__main__":
    send_webhook_test()