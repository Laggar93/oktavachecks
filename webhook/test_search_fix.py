# webhook/test_search_fix.py
import requests
import json
import re
from django.conf import settings


def test_search_fix():
    """Тест исправленного поиска"""

    print("\n🧪 ТЕСТ ИСПРАВЛЕННОГО ПОИСКА")
    print("=" * 50)

    subdomain = settings.AMOCRM_SUBDOMAIN
    token = settings.AMOCRM_ACCESS_TOKEN
    base_url = f"https://{subdomain}.amocrm.ru/api/v4"

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    # Тестовые данные
    test_cases = [
        {
            "order_id": "RAD-123456-789",
            "expected_search": ["RAD-123456-789", "123456", "123456"]
        },
        {
            "order_id": "TEST-ORDER-999",
            "expected_search": ["TEST-ORDER-999", "999", "999"]
        },
        {
            "order_id": "ABC-777-DEF",
            "expected_search": ["ABC-777-DEF", "777", "777"]
        }
    ]

    for test in test_cases:
        order_id = test["order_id"]
        print(f"\n📋 Order ID: '{order_id}'")

        # Извлекаем цифры
        numbers = re.findall(r'\d+', order_id)
        print(f"   Цифры: {numbers}")

        for search_query in test["expected_search"]:
            print(f"\n   🔍 Поиск: '{search_query}'")

            try:
                response = requests.get(
                    f"{base_url}/leads?query={search_query}&with=custom_fields",
                    headers=headers,
                    timeout=10
                )

                if response.status_code == 200:
                    data = response.json()
                    leads = data.get('_embedded', {}).get('leads', [])

                    if leads:
                        print(f"      ✅ Найдено: {len(leads)} сделок")
                        for lead in leads[:2]:
                            print(f"        - ID: {lead['id']}, Название: {lead.get('name', 'N/A')[:50]}")

                            # Проверяем поле 986103
                            if 'custom_fields_values' in lead:
                                for field in lead['custom_fields_values']:
                                    if field.get('field_id') == 986103:
                                        value = field.get('values', [{}])[0].get('value')
                                        print(f"          Поле 986103: {value} (тип: {type(value).__name__})")
                    else:
                        print(f"      ℹ️ Не найдено сделок")

                else:
                    print(f"      ❌ Ошибка: {response.status_code}")

            except Exception as e:
                print(f"      ❌ Исключение: {e}")

# Запуск в Django shell
# >>> from webhook.test_search_fix import test_search_fix
# >>> test_search_fix()