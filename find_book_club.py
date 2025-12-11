# webhook/find_book_club.py
import requests
from django.conf import settings


def find_book_club_id():
    """Найти ID для 'Книжный клуб'"""
    print("\n🔎 ПОИСК 'КНИЖНЫЙ КЛУБ' В AMOCRM")
    print("=" * 50)

    subdomain = settings.AMOCRM_SUBDOMAIN
    token = settings.AMOCRM_ACCESS_TOKEN

    # Поле "Тип события"
    field_id = 986255

    url = f"https://{subdomain}.amocrm.ru/api/v4/leads/custom_fields/{field_id}"
    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            field = response.json()
            enums = field.get('enums', [])

            print(f"🔍 Ищу в поле: {field.get('name', 'N/A')}")
            print(f"   Всего вариантов: {len(enums)}")
            print("\n📋 Результаты поиска:")
            print("-" * 40)

            found = False
            for enum in enums:
                enum_value = enum.get('value', '').lower()
                enum_id = enum.get('id')

                # Ищем по ключевым словам
                keywords = ['книж', 'book', 'литератур', 'чтение']

                for keyword in keywords:
                    if keyword in enum_value:
                        print(f"✅ СОВПАДЕНИЕ: ID {enum_id} - '{enum.get('value', 'N/A')}'")
                        found = True
                        break

            if not found:
                print("❌ 'Книжный клуб' не найден")
                print("\n📋 Все доступные варианты:")
                for enum in sorted(enums, key=lambda x: x.get('id', 0)):
                    print(f"   ID: {enum.get('id'):8} - {enum.get('value', 'N/A')}")

        else:
            print(f"❌ Ошибка: {response.status_code}")

    except Exception as e:
        print(f"❌ Исключение: {e}")

# Запуск:
# >>> from webhook.find_book_club import find_book_club_id
# >>> find_book_club_id()