import requests
import logging
import json
import time
import re
from datetime import datetime
from django.conf import settings
from .utils import format_name_for_amocrm

logger = logging.getLogger(__name__)


class AmoCRMClientKlaster:
    """
    Клиент amoCRM для воронки Кластер (pipeline_id: 10765454)
    """

    PIPELINE_ID = 10765454
    STATUS_NEW = 84775518        # Новая заявка
    STATUS_CLOSED = 143          # Закрыто и не реализовано
    LOSS_REASON_REFUND = 993033  # Причина отказа: Возврат

    def __init__(self):
        self.subdomain = settings.AMOCRM_SUBDOMAIN
        self.base_url = f"https://{self.subdomain}.amocrm.ru/api/v4"
        self.access_token = settings.AMOCRM_ACCESS_TOKEN

    def _make_request(self, method, endpoint, data=None):
        url = f"{self.base_url}/{endpoint}"
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

        logger.info(f"🔍 [Кластер] API Request: {method} {url}")
        if data:
            logger.info(f"📦 [Кластер] Request data preview: {json.dumps(data, indent=2, ensure_ascii=False)[:1000]}")

        try:
            response = requests.request(method, url, headers=headers, json=data, timeout=30)

            logger.info(f"📥 [Кластер] Response status: {response.status_code}")

            if response.status_code >= 400:
                logger.error(f"❌ [Кластер] API Error Response: {response.text}")
                try:
                    error_json = response.json()
                    logger.error(f"❌ [Кластер] Error details: {json.dumps(error_json, indent=2, ensure_ascii=False)}")
                except:
                    pass

            if response.status_code == 401:
                logger.error("[Кластер] Долгосрочный токен истек или неверный!")
                raise Exception(f"Token invalid: {response.text}")

            response.raise_for_status()

            if response.content:
                return response.json()
            return {}

        except Exception as e:
            logger.error(f"[Кластер] AmoCRM API error: {e}")
            raise

    # -------------------------------------------------------------------------
    # Контакты
    # -------------------------------------------------------------------------

    def find_contact_by_email(self, email):
        try:
            endpoint = f"contacts?query={email}"
            data = self._make_request('GET', endpoint)
            return data['_embedded']['contacts'][0] if data.get('_embedded', {}).get('contacts') else None
        except Exception as e:
            logger.error(f"[Кластер] Error finding contact by email {email}: {e}")
            return None

    def find_contact_by_phone(self, phone):
        """Поиск контакта по телефону"""
        if not phone:
            return None
        try:
            clean_phone = re.sub(r'\D', '', phone)
            endpoint = f"contacts?query={clean_phone}"
            data = self._make_request('GET', endpoint)
            return data['_embedded']['contacts'][0] if data.get('_embedded', {}).get('contacts') else None
        except Exception as e:
            logger.error(f"[Кластер] Error finding contact by phone {phone}: {e}")
            return None

    def create_contact(self, email, name, phone=None, is_agree_ads=False):
        """Создает контакт в amoCRM"""
        formatted_name = format_name_for_amocrm(name)

        contact_data = {
            "name": formatted_name,
            "custom_fields_values": [
                {
                    "field_id": 648999,  # Email (Кластер)
                    "values": [{"value": email, "enum_code": "WORK"}]
                }
            ]
        }

        if phone:
            contact_data["custom_fields_values"].append({
                "field_id": 648997,  # Phone (Кластер)
                "values": [{"value": phone, "enum_code": "WORK"}]
            })

        # Согласие на рассылку
        if isinstance(is_agree_ads, str):
            is_agree_ads = is_agree_ads.lower() == 'true'
        is_agree_ads = bool(is_agree_ads)

        contact_data["custom_fields_values"].append({
            "field_id": 989771,
            "values": [{"enum_id": 989895 if is_agree_ads else 989897}]
        })

        logger.info(f"[Кластер] 📧 Создание контакта: email={email}, is_agree_ads={is_agree_ads}")

        try:
            data = self._make_request('POST', 'contacts', [contact_data])
            contact = data['_embedded']['contacts'][0]
            logger.info(f"[Кластер] ✅ Контакт создан: {contact['id']}")
            return contact
        except Exception as e:
            logger.error(f"[Кластер] ❌ Ошибка создания контакта: {e}")
            raise

    def update_contact(self, contact_id, customer_info):
        """Обновляет существующий контакт"""
        update_data = {
            "id": contact_id,
            "custom_fields_values": []
        }

        if 'is_agree_ads' in customer_info:
            is_agree_ads = customer_info.get('is_agree_ads', False)
            if isinstance(is_agree_ads, str):
                is_agree_ads = is_agree_ads.lower() == 'true'
            is_agree_ads = bool(is_agree_ads)

            update_data["custom_fields_values"].append({
                "field_id": 989771,
                "values": [{"enum_id": 989895 if is_agree_ads else 989897}]
            })

        if not update_data["custom_fields_values"]:
            logger.info(f"[Кластер] ℹ️ Нет полей для обновления контакта {contact_id}")
            return None

        try:
            data = self._make_request('PATCH', f'contacts/{contact_id}', update_data)
            logger.info(f"[Кластер] ✅ Контакт {contact_id} обновлен")
            return data
        except Exception as e:
            logger.error(f"[Кластер] ❌ Ошибка обновления контакта {contact_id}: {e}")
            raise

    # -------------------------------------------------------------------------
    # Сделки
    # -------------------------------------------------------------------------

    def find_lead_by_order_id(self, order_id):
        try:
            logger.info(f"[Кластер] 🔍 Поиск сделки: {order_id}")

            clean_order_id = str(order_id).replace('$(date +%s)', '').replace('$(date)', '')
            endpoint = f"leads?query={clean_order_id}&with=custom_fields"
            data = self._make_request('GET', endpoint)

            if not data or '_embedded' not in data or 'leads' not in data['_embedded']:
                logger.info(f"[Кластер] Не найдено сделок для: {clean_order_id}")
                return None

            leads = data['_embedded']['leads']
            # Фильтруем только сделки из воронки Кластер
            klaster_leads = [l for l in leads if l.get('pipeline_id') == self.PIPELINE_ID]

            if klaster_leads:
                logger.info(f"[Кластер] Найдено сделок: {len(klaster_leads)}, беру первую")
                return klaster_leads[0]

            return None

        except Exception as e:
            logger.error(f"[Кластер] Ошибка поиска: {e}")
            return None

    def create_lead_with_custom_fields(self, contact_id, customer_info):
        """Создает сделку в воронке Кластер"""

        # Тип события
        event_type = self._map_event_type(customer_info.get('event_title', ''))
        event_enum_id = self._get_event_type_enum_id(event_type)

        # Источник заказа
        source_label = customer_info.get('source', 'Radario')
        source_enum_id = self._get_source_enum_id(customer_info)

        # Статус платежа
        payment_status = self._map_status_for_field(
            customer_info.get('status', ''),
            customer_info.get('payment_system_status', '')
        )
        status_enum_id = self._get_status_enum_id(payment_status)

        # Название сделки: [Источник заказа] оплата [Тип события]
        lead_name = f"{source_label} оплата {event_type}"
        lead_name = lead_name[:255]

        # Цена
        price = int(float(customer_info.get('amount', 0)))

        # Кастомные поля сделки
        custom_fields_values = []

        # 1. Номер заказа (986103)
        if customer_info.get('order_id'):
            order_id_str = str(customer_info['order_id'])
            if re.search(r'[A-Za-z]+-\d+', order_id_str):
                parts = order_id_str.split('-')
                order_id_value = parts[-1] if len(parts) > 1 else order_id_str
            else:
                order_id_value = str(abs(hash(order_id_str)) % 1000000)

            custom_fields_values.append({
                "field_id": 986103,
                "values": [{"value": order_id_value}]
            })

        # 2. Тип события (986255)
        if event_enum_id:
            custom_fields_values.append({
                "field_id": 986255,
                "values": [{"enum_id": event_enum_id}]
            })

        # 3. Название мероприятия (986251)
        if customer_info.get('event_title'):
            custom_fields_values.append({
                "field_id": 986251,
                "values": [{"value": str(customer_info['event_title'])[:100]}]
            })

        # 4. Тип билета (987187) — поле только для воронки Кластер
        if customer_info.get('ticket_type'):
            custom_fields_values.append({
                "field_id": 987187,
                "values": [{"value": str(customer_info['ticket_type'])[:255]}]
            })

        # 5. Дата и время начала события (976983)
        if customer_info.get('event_date'):
            timestamp = self._convert_to_timestamp(customer_info['event_date'])
            if timestamp:
                custom_fields_values.append({
                    "field_id": 976983,
                    "values": [{"value": timestamp}]
                })

        # 6. Дата и время создания заказа (986101)
        #    В воронке Кластер это дата создания, не дата оплаты
        if customer_info.get('creation_date'):
            timestamp = self._convert_to_timestamp(customer_info['creation_date'])
            if timestamp:
                custom_fields_values.append({
                    "field_id": 986101,
                    "values": [{"value": timestamp}]
                })

        # 7. Источник заказа (986099)
        if source_enum_id:
            custom_fields_values.append({
                "field_id": 986099,
                "values": [{"enum_id": source_enum_id}]
            })

        # 8. Статус платежа (986105)
        if status_enum_id:
            custom_fields_values.append({
                "field_id": 986105,
                "values": [{"enum_id": status_enum_id}]
            })

        # 9. Количество билетов (986253)
        if customer_info.get('tickets_count', 0) > 0:
            custom_fields_values.append({
                "field_id": 986253,
                "values": [{"value": customer_info['tickets_count']}]
            })

        # 10. Дата возврата (986123) — если это возврат
        if customer_info.get('status') == 'Refunded' or customer_info.get('payment_system_status') == 'Refund':
            refund_timestamp = int(time.time())
            if customer_info.get('refund_date'):
                refund_timestamp = self._convert_to_timestamp(customer_info['refund_date'])

            custom_fields_values.append({
                "field_id": 986123,
                "values": [{"value": refund_timestamp}]
            })

        lead_data = {
            "name": lead_name,
            "price": price,
            "pipeline_id": self.PIPELINE_ID,
            "status_id": self.STATUS_NEW,
            "_embedded": {
                "contacts": [{"id": contact_id}]
            }
        }

        if custom_fields_values:
            lead_data["custom_fields_values"] = custom_fields_values

        logger.info(f"[Кластер] 🚀 Создаю сделку '{lead_name}' с {len(custom_fields_values)} полями")

        try:
            data = self._make_request('POST', 'leads', [lead_data])

            if data and '_embedded' in data and 'leads' in data['_embedded']:
                lead = data['_embedded']['leads'][0]
                logger.info(f"[Кластер] ✅ Сделка создана: {lead['id']}")
                return lead
            else:
                logger.error(f"[Кластер] ❌ Неожиданный ответ от API: {data}")
                raise Exception(f"Unexpected API response: {data}")

        except Exception as e:
            logger.error(f"[Кластер] ❌ Ошибка создания сделки: {e}")
            raise

    def update_lead(self, lead_id, customer_info, status_id=None):
        """Обновляет существующую сделку"""
        payment_status = self._map_status_for_field(
            customer_info.get('status', ''),
            customer_info.get('payment_system_status', '')
        )
        status_enum_id = self._get_status_enum_id(payment_status)

        update_data = {
            "id": lead_id,
            "price": int(float(customer_info.get('amount', 0))),
        }

        if status_id:
            update_data["status_id"] = status_id

        custom_fields = []

        if status_enum_id:
            custom_fields.append({
                "field_id": 986105,
                "values": [{"enum_id": status_enum_id}]
            })

        if customer_info.get('tickets_count', 0) > 0:
            custom_fields.append({
                "field_id": 986253,
                "values": [{"value": customer_info['tickets_count']}]
            })

        if custom_fields:
            update_data["custom_fields_values"] = custom_fields

        logger.info(f"[Кластер] 📝 Обновляю сделку {lead_id}")

        try:
            data = self._make_request('PATCH', f'leads/{lead_id}', update_data)
            logger.info(f"[Кластер] ✅ Сделка {lead_id} обновлена")
            return data
        except Exception as e:
            logger.error(f"[Кластер] ❌ Ошибка обновления сделки {lead_id}: {e}")
            raise

    def update_lead_for_refund(self, lead_id, customer_info):
        """Обновляет сделку при возврате — переводит в Закрыто и не реализовано"""
        payment_status = self._map_status_for_field(
            customer_info.get('status', ''),
            customer_info.get('payment_system_status', '')
        )
        status_enum_id = self._get_status_enum_id(payment_status)

        update_data = {
            "status_id": self.STATUS_CLOSED,
            "loss_reason_id": self.LOSS_REASON_REFUND
        }

        custom_fields = []

        if status_enum_id:
            custom_fields.append({
                "field_id": 986105,
                "values": [{"enum_id": status_enum_id}]
            })

        # Дата возврата (986123)
        refund_timestamp = int(time.time())
        if customer_info.get('refund_date'):
            refund_timestamp = self._convert_to_timestamp(customer_info['refund_date'])

        custom_fields.append({
            "field_id": 986123,
            "values": [{"value": refund_timestamp}]
        })

        if custom_fields:
            update_data["custom_fields_values"] = custom_fields

        logger.info(f"[Кластер] 🔄 Обновляю сделку {lead_id} для возврата")

        try:
            data = self._make_request('PATCH', f'leads/{lead_id}', update_data)
            logger.info(f"[Кластер] ✅ Сделка {lead_id} переведена в возврат")
            return data
        except Exception as e:
            logger.error(f"[Кластер] ❌ Ошибка обновления сделки {lead_id} для возврата: {e}")
            raise

    # -------------------------------------------------------------------------
    # Маппинги
    # -------------------------------------------------------------------------

    def _get_source_enum_id(self, customer_info):
        """enum_id для поля Источник заказа (986099)"""
        return 985093  # Онлайн — аналогично старой интеграции

    def _map_event_type(self, event_title):
        if not event_title:
            return 'Другое'

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
            'диалог': 'Диалог',
            'книжный клуб': 'Книжный клуб',
            'book club': 'Книжный клуб',
            'bookclub': 'Книжный клуб',
        }

        for key, value in mapping.items():
            if key in event_title_lower:
                return value

        return 'Другое'

    def _get_event_type_enum_id(self, event_type):
        mapping = {
            'Мастер-класс': 985177,
            'Программа': 985179,
            'Лекция': 985181,
            'Театральное занятие': 985183,
            'Игра': 985185,
            'Резиденция': 985187,
            'Выставка': 985189,
            'Спектакль': 985191,
            'Экскурсия': 985193,
            'Концерт': 985195,
            'Шоу': 985197,
            'Комбо': 985199,
            'Кинопоказ': 985201,
            'Конференция': 985203,
            'Фестиваль': 985205,
            'Творческая встреча': 985207,
            'Кинофестиваль': 985209,
            'Открытый разговор': 985211,
            'Митап': 985213,
            'Дискуссия': 985215,
            'Встреча': 985217,
            'Перформанс': 985219,
            'Workshop': 985221,
            'Воркшоп': 985223,
            'Арт-терапия': 985225,
            'Занятие': 985227,
            'Паблик-топ': 985229,
            'TED-talk': 985231,
            'Показ': 985233,
            'Диалог': 985235,
            'Книжный клуб': 986271,
            'Другое': None
        }
        return mapping.get(event_type, None)

    def _map_status_for_field(self, status, payment_system_status):
        if status == 'Paid' and payment_system_status == 'Paid':
            return 'Оплачен'
        elif status in ('Refund', 'Refunded') or payment_system_status == 'Refund':
            return 'Возврат'
        elif status == 'Pending':
            return 'В обработке'
        elif status == 'Cancelled':
            return 'Отменен'
        else:
            return 'Неизвестно'

    def _get_status_enum_id(self, status):
        mapping = {
            'Оплачен': 985097,
            'Возврат': 985099,
            'В обработке': None,
            'Отменен': None,
            'Неизвестно': None
        }
        return mapping.get(status, None)

    def _convert_to_timestamp(self, date_string):
        if not date_string:
            return int(time.time())

        try:
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

            return int(time.time())

        except Exception:
            return int(time.time())