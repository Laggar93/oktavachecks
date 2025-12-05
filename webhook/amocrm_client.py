import requests
import logging
import json
import time
from datetime import datetime
from django.conf import settings

logger = logging.getLogger(__name__)


class AmoCRMClient:
    def __init__(self):
        self.subdomain = settings.AMOCRM_SUBDOMAIN
        self.base_url = f"https://{self.subdomain}.amocrm.ru/api/v4"
        self.access_token = settings.AMOCRM_ACCESS_TOKEN

    def _make_request(self, method, endpoint, data=None):
        """Упрощенный запрос"""
        url = f"{self.base_url}/{endpoint}"
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

        try:
            response = requests.request(method, url, headers=headers, json=data, timeout=30)

            if response.status_code == 401:
                logger.error("Долгосрочный токен истек или неверный! Нужно обновить токен в amoCRM.")
                logger.error(f"Полный ответ: {response.text}")
                raise Exception(f"Token invalid: {response.text}")

            response.raise_for_status()

            if response.content:
                return response.json()
            return {}

        except Exception as e:
            logger.error(f"AmoCRM API error: {e}")
            raise

    def find_contact_by_email(self, email):
        """Поиск контакта по email"""
        try:
            endpoint = f"contacts?query={email}"
            data = self._make_request('GET', endpoint)
            return data['_embedded']['contacts'][0] if data.get('_embedded', {}).get('contacts') else None
        except Exception as e:
            logger.error(f"Error finding contact by email {email}: {e}")
            return None

    def create_lead(self, contact_id, lead_name, amount):
        """Простой метод создания сделки для тестирования"""
        # Сумма в копейках
        price = int(float(amount))

        lead_data = {
            "name": lead_name,
            "price": price,
            "pipeline_id": 9713218,  # Воронка "Музей" ✓
            "status_id": 77419554,  # Этап "Новая заявка" ✓
            "_embedded": {
                "contacts": [{"id": contact_id}]
            }
        }

        try:
            data = self._make_request('POST', 'leads', [lead_data])
            return data['_embedded']['leads'][0]
        except Exception as e:
            logger.error(f"Error creating lead: {e}")
            raise

    def find_contact_by_phone(self, phone):
        """Поиск контакта по телефону"""
        try:
            # Нужно настроить поиск по телефону
            # Можно искать через кастомные поля
            return None
        except Exception as e:
            logger.error(f"Error finding contact by phone {phone}: {e}")
            return None

    def create_contact(self, email, name, phone=None):
        """Создание нового контакта"""
        contact_data = {
            "name": name,  # Имя контакта передается правильно
            "custom_fields_values": [
                {
                    "field_code": "EMAIL",
                    "values": [{"value": email, "enum_code": "WORK"}]
                }
            ]
        }

        if phone:
            contact_data["custom_fields_values"].append({
                "field_code": "PHONE",
                "values": [{"value": phone, "enum_code": "WORK"}]
            })

        try:
            data = self._make_request('POST', 'contacts', [contact_data])
            return data['_embedded']['contacts'][0]
        except Exception as e:
            logger.error(f"Error creating contact: {e}")
            raise

    def find_lead_by_order_id(self, order_id):
        """Поиск сделки по номеру заказа"""
        try:
            # Поиск сделки по кастомному полю "Номер заказа" (986103)
            endpoint = f"leads?filter[custom_fields_values][0][field_id]=986103&filter[custom_fields_values][0][values][0][value]={order_id}"
            data = self._make_request('GET', endpoint)
            return data['_embedded']['leads'][0] if data.get('_embedded', {}).get('leads') else None
        except Exception as e:
            logger.error(f"Error finding lead by order_id {order_id}: {e}")
            return None

    def _map_event_type(self, event_title):
        """Сопоставление типа события по ТЗ"""
        event_title_lower = event_title.lower()

        mapping = {
            'мастер-класс': 'Мастер-класс',
            'мастер класс': 'Мастер-класс',
            'программа': 'Программа',
            'лекция': 'Лекция',
            'театральное занятие': 'Театральное занятие',
            'игра': 'Игра',
            'резиденция': 'Резиденция',
            'выставка': 'Выставка',
            'спектакль': 'Спектакль',
            'экскурсия': 'Экскурсия',
            'концерт': 'Концерт',
            'шоу': 'Шоу',
            'комбо': 'Комбо',
            'кинопоказ': 'Кинопоказ',
            'конференция': 'Конференция',
            'фестиваль': 'Фестиваль',
            'творческая встреча': 'Творческая встреча',
            'кинофестиваль': 'Кинофестиваль',
            'открытый разговор': 'Открытый разговор',
            'митап': 'Митап',
            'мит-ап': 'Митап',
            'дискуссия': 'Дискуссия',
            'встреча': 'Встреча',
            'перформанс': 'Перформанс',
            'workshop': 'Workshop',
            'воркшоп': 'Воркшоп',
            'арт-терапия': 'Арт-терапия',
            'занятие': 'Занятие',
            'паблик-ток': 'Паблик-топ',
            'ted-talk': 'TED-talk',
            'показ': 'Показ',
            'диалог': 'Диалог'
        }

        for key, value in mapping.items():
            if key in event_title_lower:
                return value

        # Если не нашли соответствие, пытаемся определить по словам
        for key in mapping.keys():
            if key.replace('-', ' ') in event_title_lower:
                return mapping[key]

        return 'Другое'

    def _convert_to_timestamp(self, date_string):
        """Конвертация даты из Radario в timestamp"""
        if not date_string:
            return int(time.time())

        try:
            # Пробуем разные форматы дат
            formats = [
                '%Y-%m-%dT%H:%M:%S.%fZ',
                '%Y-%m-%dT%H:%M:%SZ',
                '%Y-%m-%d %H:%M:%S',
                '%d.%m.%Y %H:%M:%S'
            ]

            for fmt in formats:
                try:
                    dt = datetime.strptime(date_string, fmt)
                    return int(dt.timestamp())
                except ValueError:
                    continue

            # Если не удалось распарсить, возвращаем текущее время
            return int(time.time())

        except Exception:
            return int(time.time())

    def create_lead_with_custom_fields(self, contact_id, customer_info):
        """Создание сделки со всеми кастомными полями по ТЗ"""

        # Определяем тип события
        event_type = self._map_event_type(customer_info['event_title'])

        # Название сделки по маске: [Источник заказа] оплата [Тип события]
        lead_name = f"[{customer_info['source']}] оплата [{event_type}]"

        # Сумма в копейках
        price = int(customer_info['amount'])

        # Статус и этап
        is_paid = (customer_info['status'] == 'Paid' and
                   customer_info['payment_system_status'] == 'Paid')

        pipeline_id = 9713218  # Воронка "Музей"

        if is_paid:
            status_id = 77419554  # Новая заявка
        else:
            status_id = 142  # Первичный контакт (или другой дефолтный)

        # Подготавливаем кастомные поля (исправленные ID согласно реальным полям в amoCRM)
        custom_fields = [
            # Номер заказа - id: 986103, тип: Число ✓
            {
                "field_id": 986103,
                "values": [{"value": customer_info['order_id']}]
            },
            # Тип события - id: 986255, тип: Список ✓
            {
                "field_id": 986255,
                "values": [{"enum_id": self._get_event_type_enum_id(event_type)}]
            },
            # Событие - id: 986251, тип: Текст ✓
            {
                "field_id": 986251,
                "values": [{"value": customer_info['event_title'][:100]}]
            },
            # Дата и время начала события - id: 976983 ✓ (Дата и время записи)
            {
                "field_id": 976983,
                "values": [{"value": self._convert_to_timestamp(customer_info['event_date'])}]
            },
            # Дата и время оплаты - id: 986101, тип: date_time ✓ (исправлено!)
            {
                "field_id": 986101,
                "values": [{"value": self._convert_to_timestamp(customer_info['payment_date'])}]
            },
            # Вид оплаты - id: 986099, тип: select ✓ (исправлено! было "Источник заказа")
            {
                "field_id": 976809,  # "Источник" (используем для источника заказа)
                "values": [{"value": customer_info['source']}]  # "Radario"
            },
            {
                "field_id": 986099,  # "Вид оплаты" (заполняем значением "Онлайн")
                "values": [{"value": "Онлайн"}]  # Все оплаты онлайн через Радарио
            },
            # Статус оплаты - id: 986105, тип: select ✓
            {
                "field_id": 986105,
                "values": [{"enum_id": self._get_status_enum_id(
                    self._map_status_for_field(
                        customer_info['status'],
                        customer_info['payment_system_status']
                    )
                )}]
            },
            # Количество билетов - id: 986253, тип: numeric ✓
            {
                "field_id": 986253,
                "values": [{"value": customer_info['tickets_count']}]
            }
        ]

        # Добавляем телефон и email если они есть в контакте
        # Телефон - id: 648997 (если поле существует в сделках)
        if customer_info.get('phone'):
            custom_fields.append({
                "field_id": 648997,  # Проверь, существует ли это поле в сделках!
                "values": [{"value": customer_info['phone']}]
            })

        # Почта - id: 648999 (если поле существует в сделках)
        custom_fields.append({
            "field_id": 648999,  # Проверь, существует ли это поле в сделках!
            "values": [{"value": customer_info['email']}]
        })

        # Добавляем дату возврата если есть
        if customer_info.get('refund_date'):
            custom_fields.append({
                "field_id": 986123,  # Дата и время возврата ✓
                "values": [{"value": self._convert_to_timestamp(customer_info['refund_date'])}]
            })
        elif customer_info.get('status') == 'Refunded' or customer_info.get('payment_system_status') == 'Refund':
            # Если статус возврата, но нет даты возврата, используем текущее время
            custom_fields.append({
                "field_id": 986123,  # Дата и время возврата
                "values": [{"value": int(time.time())}]
            })

        # Удаляем None значения
        custom_fields = [field for field in custom_fields if field is not None]

        lead_data = {
            "name": lead_name,
            "price": price,
            "pipeline_id": pipeline_id,
            "status_id": status_id,
            "custom_fields_values": custom_fields,
            "_embedded": {
                "contacts": [{"id": contact_id}]
            }
        }

        try:
            data = self._make_request('POST', 'leads', [lead_data])
            return data['_embedded']['leads'][0]
        except Exception as e:
            logger.error(f"Error creating lead with custom fields: {e}")
            raise

    def update_lead_for_refund(self, lead_id, customer_info):
        """Обновление сделки при возврате"""
        update_data = {
            "id": lead_id,
            "status_id": 143,  # Закрыто и не реализовано
            "loss_reason_id": 976851,  # Причина отказа Музей
        }

        # Добавляем дату возврата если есть
        if customer_info.get('refund_date'):
            update_data["custom_fields_values"] = [
                {
                    "field_id": 986123,  # Дата возврата
                    "values": [{"value": self._convert_to_timestamp(customer_info.get('refund_date'))}]
                }
            ]

        try:
            data = self._make_request('PATCH', f'leads/{lead_id}', update_data)
            return data
        except Exception as e:
            logger.error(f"Error updating lead for refund {lead_id}: {e}")
            raise

    def update_lead(self, lead_id, customer_info):
        """Обновление сделки при изменении статуса/суммы"""
        # Определяем статус для поля
        status_value = self._map_status_for_field(
            customer_info['status'],
            customer_info['payment_system_status']
        )

        update_data = {
            "id": lead_id,
            "price": int(customer_info['amount']),  # Обновляем сумму
            "custom_fields_values": [
                {
                    "field_id": 986105,  # Статус оплаты
                    "values": [{"enum_id": self._get_status_enum_id(status_value)}]
                }
            ]
        }

        try:
            data = self._make_request('PATCH', f'leads/{lead_id}', update_data)
            return data
        except Exception as e:
            logger.error(f"Error updating lead {lead_id}: {e}")
            raise

    def _map_status_for_field(self, status, payment_system_status):
        """Сопоставление статуса для поля 986105"""
        if status == 'Paid' and payment_system_status == 'Paid':
            return 'Оплачен'
        elif status == 'Refund' or payment_system_status == 'Refund' or status == 'Refunded':
            return 'Возврат'
        elif status == 'Pending':
            return 'В обработке'
        elif status == 'Cancelled':
            return 'Отменен'
        else:
            return 'Неизвестно'

    def _get_event_type_enum_id(self, event_type):
        """Получение enum_id для типа события"""
        # TODO: Получить реальные ID из AmoCRM
        # Временно используем заглушки
        mapping = {
            'Мастер-класс': 1,
            'Программа': 2,
            'Лекция': 3,
            'Театральное занятие': 4,
            'Игра': 5,
            'Резиденция': 6,
            'Выставка': 7,
            'Спектакль': 8,
            'Экскурсия': 9,
            'Концерт': 10,
            'Шоу': 11,
            'Комбо': 12,
            'Кинопоказ': 13,
            'Конференция': 14,
            'Фестиваль': 15,
            'Творческая встреча': 16,
            'Кинофестиваль': 17,
            'Открытый разговор': 18,
            'Митап': 19,
            'Дискуссия': 20,
            'Встреча': 21,
            'Перформанс': 22,
            'Workshop': 23,
            'Воркшоп': 24,
            'Арт-терапия': 25,
            'Занятие': 26,
            'Паблик-топ': 27,
            'TED-talk': 28,
            'Показ': 29,
            'Диалог': 30,
            'Другое': 31
        }
        return mapping.get(event_type, 31)  # По умолчанию "Другое"

    def _get_source_enum_id(self, source):
        """Получение enum_id для источника заказа"""
        # Теперь не используется, так как поле 986099 оказалось "Вид оплаты"
        return 1  # Заглушка

    def _get_status_enum_id(self, status):
        """Получение enum_id для статуса"""
        # TODO: Получить реальные ID
        mapping = {
            'Оплачен': 1,
            'Возврат': 2,
            'В обработке': 3,
            'Отменен': 4,
            'Неизвестно': 5
        }
        return mapping.get(status, 5)