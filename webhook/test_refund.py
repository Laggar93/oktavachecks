# webhook/test_refund.py
import requests
import json
import time

WEBHOOK_URL = "http://oktavachecks.twc1.net/webhook/radario/"


def test_refund(order_id, contact_id, lead_id):
    """Тест возврата денег на существующий заказ"""

    print(f"\n🔄 Тестируем возврат для заказа: {order_id}")
    print(f"Contact ID: {contact_id}")
    print(f"Lead ID: {lead_id}")

    refund_data = {
        "model": {
            "Id": order_id,  # Тот же order_id
            "Email": "test_webhook@example.com",  # Тот же email
            "Status": "Refunded",
            "PaymentSystemStatus": "Refund",
            "Amount": 0.00,  # Сумма возврата 0
            "Currency": "RUB",
            "CreationDate": "2024-01-15T10:30:00Z",
            "PaymentDate": "2024-01-15T10:35:00Z",
            "UpdateDate": "2024-01-16T14:20:00Z",  # Новая дата обновления
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
            ],
            "RefundDetails": {
                "RefundDate": "2024-01-16T14:15:00Z",
                "RefundAmount": 2999.99,
                "RefundReason": "Отмена по инициативе клиента"
            }
        }
    }

    print(f"\n📤 Отправляю вебхук возврата...")

    response = requests.post(
        WEBHOOK_URL,
        json=refund_data,
        headers={'Content-Type': 'application/json'},
        timeout=30
    )

    print(f"Статус: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"✅ Возврат обработан успешно!")
        print(f"Contact ID: {result.get('contact_id')}")
        print(f"Lead ID: {result.get('lead_id')}")

        # Проверяем, что это тот же lead_id
        if result.get('lead_id') == lead_id:
            print(f"✅ Обработана существующая сделка {lead_id}")
        else:
            print(f"⚠️ Создана новая сделка: {result.get('lead_id')}")

    else:
        print(f"❌ Ошибка: {response.text}")

    return response


def test_multiple_scenarios():
    """Тест нескольких сценариев"""

    print("=" * 50)
    print("🧪 ТЕСТИРОВАНИЕ РАЗНЫХ СЦЕНАРИЕВ")
    print("=" * 50)

    # Сценарий 1: Новый заказ с оплатой
    print("\n1. 📝 НОВЫЙ ЗАКАЗ (Paid)")
    order_id_1 = f"RAD-{int(time.time())}-001"

    data_1 = {
        "model": {
            "Id": order_id_1,
            "Email": f"test_{int(time.time())}@example.com",
            "Status": "Paid",
            "PaymentSystemStatus": "Paid",
            "Amount": 1500.00,
            "User": {"Name": "Новый Клиент"},
            "Event": {"Title": "Новое мероприятие"}
        }
    }

    response_1 = requests.post(WEBHOOK_URL, json=data_1, headers={'Content-Type': 'application/json'})
    print(f"Статус: {response_1.status_code}")

    if response_1.status_code == 200:
        result_1 = response_1.json()
        print(f"✅ Создана сделка: {result_1.get('lead_id')}")

        # Ждем 2 секунды
        time.sleep(2)

        # Сценарий 2: Возврат на этот заказ
        print(f"\n2. 🔄 ВОЗВРАТ на заказ {order_id_1}")
        refund_response = test_refund(
            order_id=order_id_1,
            contact_id=result_1.get('contact_id'),
            lead_id=result_1.get('lead_id')
        )

    # Сценарий 3: Заказ в статусе Pending
    print(f"\n3. ⏳ ЗАКАЗ в статусе Pending")
    order_id_2 = f"RAD-{int(time.time())}-002"

    data_3 = {
        "model": {
            "Id": order_id_2,
            "Email": f"pending_{int(time.time())}@example.com",
            "Status": "Pending",
            "PaymentSystemStatus": "Pending",
            "Amount": 2000.00,
            "User": {"Name": "Ожидающий Клиент"},
            "Event": {"Title": "Ожидаемое мероприятие"}
        }
    }

    response_3 = requests.post(WEBHOOK_URL, json=data_3, headers={'Content-Type': 'application/json'})
    print(f"Статус: {response_3.status_code}")

    if response_3.status_code == 200:
        result_3 = response_3.json()
        print(f"✅ Создана сделка: {result_3.get('lead_id')}")


# Запуск тестов
if __name__ == "__main__":
    # Сначала тестируем возврат на созданный ранее заказ
    test_refund(
        order_id="RAD-123456-789",  # Тот же order_id
        contact_id=48390783,  # Contact ID из предыдущего теста
        lead_id=33821137  # Lead ID из предыдущего теста
    )

    # Затем тестируем разные сценарии
    print("\n" + "=" * 50)
    test_multiple_scenarios()