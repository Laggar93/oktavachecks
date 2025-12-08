# webhook/debug_lead_field.py
import requests
import json
from oktavachecks.config import AMOCRM_ACCESS_TOKEN


def check_lead_field(lead_id):
    """Проверить какое значение сохранено в поле 986103"""

    # Используйте ваш реальный токен
    subdomain = "infooktavaklasterru"
    token = AMOCRM_ACCESS_TOKEN  # Получите из settings или окружения

    url = f"https://{subdomain}.amocrm.ru/api/v4/leads/{lead_id}?with=custom_fields"

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            lead = response.json()
            print(f"\n🔍 Проверяем сделку {lead_id}:")
            print(f"Название: {lead.get('name')}")

            # Ищем поле 986103
            if 'custom_fields_values' in lead:
                for field in lead['custom_fields_values']:
                    if field.get('field_id') == 986103:
                        value = field.get('values', [{}])[0].get('value')
                        print(f"\n✅ Поле 986103 найдено!")
                        print(f"   Значение: {value}")
                        print(f"   Тип значения: {type(value)}")
                        return value

                print(f"\n⚠️ Поле 986103 не найдено в сделке")
                print(f"   Доступные поля:")
                for field in lead['custom_fields_values']:
                    print(f"   - Поле {field.get('field_id')}: {field.get('values', [{}])[0].get('value')}")
            else:
                print(f"\n❌ В сделке нет кастомных полей")

        else:
            print(f"❌ Ошибка запроса: {response.status_code}")
            print(f"   {response.text}")

    except Exception as e:
        print(f"❌ Исключение: {e}")


# Проверим обе сделки
print("Проверяем исходную сделку (33821137):")
check_lead_field(33821137)

print("\n" + "=" * 50 + "\n")

print("Проверяем новую сделку при возврате (33821161):")
check_lead_field(33821161)