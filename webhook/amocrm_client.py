import requests
import logging
import json
import time
import re
from datetime import datetime
from django.conf import settings
from .utils import format_name_for_amocrm, create_lead_name

logger = logging.getLogger(__name__)


class AmoCRMClient:
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

        logger.info(f"🔍 API Request: {method} {url}")
        if data:
            logger.info(f"📦 Request data preview: {json.dumps(data, indent=2, ensure_ascii=False)[:1000]}")

        try:
            response = requests.request(method, url, headers=headers, json=data, timeout=30)

            logger.info(f"📥 Response status: {response.status_code}")

            # Логируем полный ответ от amoCRM при ошибке
            if response.status_code >= 400:
                logger.error(f"❌ API Error Response: {response.text}")
                try:
                    error_json = response.json()
                    logger.error(f"❌ Error details: {json.dumps(error_json, indent=2, ensure_ascii=False)}")
                except:
                    pass

            if response.status_code == 401:
                logger.error("Долгосрочный токен истек или неверный! Нужно обновить токен в amoCRM.")
                raise Exception(f"Token invalid: {response.text}")

            response.raise_for_status()

            if response.content:
                return response.json()
            return {}

        except Exception as e:
            logger.error(f"AmoCRM API error: {e}")
            raise

    def _create_compact_description(self, customer_info, event_type, payment_status):
        info_parts = []

        if customer_info.get('order_id'):
            info_parts.append(f"Заказ: {customer_info['order_id']}")

        info_parts.append(event_type)

        if customer_info.get('event_title'):
            event_title = customer_info['event_title']
            if len(event_title) > 40:
                event_title = event_title[:37] + "..."
            info_parts.append(event_title)

        info_parts.append(payment_status)

        if customer_info.get('amount'):
            amount = float(customer_info['amount'])
            if amount >= 1000:
                amount_str = f"{amount / 1000:.0f}K руб"
            else:
                amount_str = f"{amount:.0f} руб"
            info_parts.append(amount_str)

        if customer_info.get('tickets_count', 0) > 0:
            tickets = customer_info['tickets_count']
            info_parts.append(f"{tickets} билет{'ов' if tickets > 1 else ''}")

        description = " • ".join(info_parts)
        description += " • Источник: Radario"

        if len(description) > 256:
            description = " • ".join(info_parts[:4])
            description += " • Radario"
            if len(description) > 256:
                description = description[:253] + "..."

        return description

    def find_contact_by_email(self, email):
        try:
            endpoint = f"contacts?query={email}"
            data = self._make_request('GET', endpoint)
            return data['_embedded']['contacts'][0] if data.get('_embedded', {}).get('contacts') else None
        except Exception as e:
            logger.error(f"Error finding contact by email {email}: {e}")
            return None

    def create_lead(self, contact_id, lead_name, amount):
        price = int(float(amount))

        lead_data = {
            "name": lead_name,
            "price": price,
            "pipeline_id": 9713218,
            "status_id": 77419554,
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
        try:
            return None
        except Exception as e:
            logger.error(f"Error finding contact by phone {phone}: {e}")
            return None

    def create_contact(self, email, name, phone=None, is_agree_ads=False):
        """
        Создает контакт в amoCRM с email, телефоном и согласием на рассылку
        """
        formatted_name = format_name_for_amocrm(name)

        # Базовые поля контакта
        contact_data = {
            "name": formatted_name,
            "custom_fields_values": [
                {
                    "field_code": "EMAIL",
                    "values": [{"value": email, "enum_code": "WORK"}]
                }
            ]
        }

        # Добавляем телефон, если есть
        if phone:
            contact_data["custom_fields_values"].append({
                "field_code": "PHONE",
                "values": [{"value": phone, "enum_code": "WORK"}]
            })

        # ДОБАВЛЯЕМ СОГЛАСИЕ НА РАССЫЛКУ В КОНТАКТ (поле 989771)
        if isinstance(is_agree_ads, str):
            is_agree_ads = is_agree_ads.lower() == 'true'
        is_agree_ads = bool(is_agree_ads)

        contact_data["custom_fields_values"].append({
            "field_id": 989771,  # ID поля "Согласен с рассылкой" в контактах
            "values": [
                {
                    "enum_id": 989895 if is_agree_ads else 989897  # Да/Нет
                }
            ]
        })

        logger.info(f"📧 СОЗДАНИЕ КОНТАКТА: email={email}, is_agree_ads={is_agree_ads} -> enum_id: {989895 if is_agree_ads else 989897}")

        try:
            data = self._make_request('POST', 'contacts', [contact_data])
            contact = data['_embedded']['contacts'][0]
            logger.info(f"✅ Контакт создан: {contact['id']}")
            return contact
        except Exception as e:
            logger.error(f"❌ Ошибка создания контакта: {e}")
            raise

    def update_contact(self, contact_id, customer_info):
        """
        Обновляет существующий контакт в amoCRM (согласие на рассылку)
        """
        update_data = {
            "id": contact_id,
            "custom_fields_values": []
        }

        # Обновляем согласие на рассылку, если оно есть в данных
        if 'is_agree_ads' in customer_info:
            is_agree_ads = customer_info.get('is_agree_ads', False)
            if isinstance(is_agree_ads, str):
                is_agree_ads = is_agree_ads.lower() == 'true'
            is_agree_ads = bool(is_agree_ads)

            update_data["custom_fields_values"].append({
                "field_id": 989771,
                "values": [
                    {
                        "enum_id": 989895 if is_agree_ads else 989897
                    }
                ]
            })

            logger.info(f"📧 Обновляю согласие на рассылку для контакта {contact_id}: {is_agree_ads}")

        # Если нет полей для обновления, не отправляем запрос
        if not update_data["custom_fields_values"]:
            logger.info(f"ℹ️ Нет полей для обновления контакта {contact_id}")
            return None

        try:
            data = self._make_request('PATCH', f'contacts/{contact_id}', update_data)
            logger.info(f"✅ Контакт {contact_id} обновлен")
            return data
        except Exception as e:
            logger.error(f"❌ Ошибка обновления контакта {contact_id}: {e}")
            raise

    def find_lead_by_order_id(self, order_id):
        try:
            logger.info(f"🔍 Поиск сделки: {order_id}")

            clean_order_id = str(order_id).replace('$(date +%s)', '').replace('$(date)', '')

            endpoint = f"leads?query={clean_order_id}&with=custom_fields"
            data = self._make_request('GET', endpoint)

            if not data or '_embedded' not in data or 'leads' not in data['_embedded']:
                logger.info(f"Не найдено сделок для: {clean_order_id}")
                return None

            leads = data['_embedded']['leads']

            if leads:
                logger.info(f"Найдено сделок: {len(leads)}, беру первую")
                return leads[0]

            return None

        except Exception as e:
            logger.error(f"Ошибка поиска: {e}")
            return None

    def _map_event_type(self, event_title):
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
            'литературный клуб': 'Книжный клуб',
            'литературная встреча': 'Книжный клуб',
            'чтение': 'Книжный клуб',
            'литературный вечер': 'Книжный клуб',
            'обсуждение книги': 'Книжный клуб'
        }

        for key, value in mapping.items():
            if key in event_title_lower:
                return value

        for key in mapping.keys():
            if key.replace('-', ' ') in event_title_lower:
                return mapping[key]

        return 'Другое'

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

    def create_lead_with_custom_fields(self, contact_id, customer_info):
        """
        Создает сделку в amoCRM с кастомными полями (БЕЗ поля согласия на рассылку)
        """
        # Определяем тип события
        event_type = self._map_event_type(customer_info.get('event_title', ''))
        event_enum_id = self._get_event_type_enum_id(event_type)

        # Определяем статус платежа
        payment_status = self._map_status_for_field(
            customer_info.get('status', ''),
            customer_info.get('payment_system_status', '')
        )
        status_enum_id = self._get_status_enum_id(payment_status)

        # Создаем название сделки
        lead_name = create_lead_name(
            {"Title": customer_info.get('event_title', '')},
            customer_info.get('order_id')
        )
        lead_name = lead_name[:255]

        # Цена сделки
        price = int(float(customer_info.get('amount', 0)))

        # Определяем статус воронки
        is_paid = (customer_info.get('status') == 'Paid' and
                   customer_info.get('payment_system_status') == 'Paid')
        pipeline_id = 9713218
        status_id = 77419554 if is_paid else 142

        # Создаем компактное описание
        compact_description = self._create_compact_description(
            customer_info, event_type, payment_status
        )

        # Собираем кастомные поля для сделки (БЕЗ 989771)
        custom_fields_values = []

        # 1. Номер заказа (поле 986103)
        if customer_info.get('order_id'):
            order_id_str = str(customer_info['order_id'])
            if re.search(r'[A-Za-z]+-\d+', order_id_str):
                parts = order_id_str.split('-')
                order_id_value = parts[-1] if len(parts) > 1 else order_id_str
            else:
                order_id_value = str(abs(hash(order_id_str)) % 1000000)

            logger.info(f"💳 Сохраняю order_id: '{order_id_str}' -> '{order_id_value}'")
            custom_fields_values.append({
                "field_id": 986103,
                "values": [{"value": order_id_value}]
            })

        # 2. Количество билетов (поле 986253)
        if customer_info.get('tickets_count', 0) > 0:
            custom_fields_values.append({
                "field_id": 986253,
                "values": [{"value": customer_info['tickets_count']}]
            })

        # 3. Название мероприятия (поле 986251)
        if customer_info.get('event_title'):
            custom_fields_values.append({
                "field_id": 986251,
                "values": [{"value": str(customer_info['event_title'])[:100]}]
            })

        # 4. Компактное описание (поле 976741)
        custom_fields_values.append({
            "field_id": 976741,
            "values": [{"value": compact_description}]
        })

        # 5. Тип события (поле 986255)
        if event_enum_id:
            custom_fields_values.append({
                "field_id": 986255,
                "values": [{"enum_id": event_enum_id}]
            })

        # 6. Статус платежа (поле 986105)
        if status_enum_id:
            custom_fields_values.append({
                "field_id": 986105,
                "values": [{"enum_id": status_enum_id}]
            })

        # 7. Источник (поле 976809)
        custom_fields_values.append({
            "field_id": 976809,
            "values": [{"enum_id": 973649}]  # Radario
        })

        # 8. Тип продажи (поле 986099)
        custom_fields_values.append({
            "field_id": 986099,
            "values": [{"enum_id": 985093}]  # Онлайн
        })

        # 9. Дата оплаты (поле 986101)
        # ДАТА МЕРОПРИЯТИЯ (поле 976983)
        if customer_info.get('event_date'):
            timestamp = self._convert_to_timestamp(customer_info['event_date'])
            if timestamp:
                custom_fields_values.append({
                    "field_id": 976983,
                    "values": [{"value": timestamp}]
                })
                logger.info(f"📅 ДАТА МЕРОПРИЯТИЯ (field 976983): {customer_info['event_date']}")

        # ДАТА ОПЛАТЫ (поле 986101)
        if customer_info.get('payment_date'):
            timestamp = self._convert_to_timestamp(customer_info['payment_date'])
            if timestamp:
                custom_fields_values.append({
                    "field_id": 986101,
                    "values": [{"value": timestamp}]
                })
                logger.info(f"💰 ДАТА ОПЛАТЫ (field 986101): {customer_info['payment_date']}")

        # 11. Дата возврата (поле 986123) - для возвратов
        if customer_info.get('status') == 'Refunded' or customer_info.get('payment_system_status') == 'Refund':
            refund_timestamp = int(time.time())
            if customer_info.get('refund_date'):
                refund_timestamp = self._convert_to_timestamp(customer_info['refund_date'])

            custom_fields_values.append({
                "field_id": 986123,
                "values": [{"value": refund_timestamp}]
            })

        # Формируем данные сделки
        lead_data = {
            "name": lead_name,
            "price": price,
            "pipeline_id": pipeline_id,
            "status_id": status_id,
            "_embedded": {
                "contacts": [{"id": contact_id}]
            }
        }

        if custom_fields_values:
            lead_data["custom_fields_values"] = custom_fields_values

        # Создаем примечание с полной информацией (БЕЗ согласия на рассылку - оно в контакте)
        full_note = f"""🎫 Radario #{customer_info.get('order_id', 'N/A')}
        Тип: {event_type}
        Мероприятие: {customer_info.get('event_title', 'N/A')}
        Статус: {customer_info.get('status', 'N/A')} ({customer_info.get('payment_system_status', 'N/A')})
        Сумма: {customer_info.get('amount', 0)} руб
        Билетов: {customer_info.get('tickets_count', 0)}
        Email: {customer_info.get('email', 'N/A')}
        Телефон: {customer_info.get('phone', 'N/A')}
        Дата: {customer_info.get('event_date', 'N/A')}
        Оплата: {customer_info.get('payment_date', 'N/A')}"""

        lead_data_with_notes = lead_data.copy()
        lead_data_with_notes["notes"] = [{
            "note_type": "common",
            "params": {
                "text": full_note[:4000]
            }
        }]

        logger.info(f"🚀 Создаю сделку '{lead_name}' с {len(custom_fields_values)} полями")

        # Логируем даты перед отправкой
        logger.info(f"📅 Отправляемые даты:")
        logger.info(f"   - Дата мероприятия (field 976983): {customer_info.get('event_date')}")
        logger.info(f"   - Дата оплаты (field 986101): {customer_info.get('payment_date')}")

        try:
            data = self._make_request('POST', 'leads', [lead_data_with_notes])

            if data and '_embedded' in data and 'leads' in data['_embedded']:
                lead = data['_embedded']['leads'][0]
                logger.info(f"✅ Сделка создана: {lead['id']}")
                return lead
            else:
                logger.error(f"❌ Неожиданный ответ от API: {data}")
                raise Exception(f"Unexpected API response: {data}")

        except Exception as e:
            logger.error(f"❌ Ошибка создания сделки: {e}")
            if hasattr(e, 'response') and e.response:
                try:
                    error_data = e.response.json()
                    logger.error(f"Ответ API: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
                except:
                    logger.error(f"Текст ответа: {e.response.text}")
            raise

    def update_lead_for_refund(self, lead_id, customer_info):
        """
        Обновляет сделку при возврате средств (БЕЗ обновления согласия на рассылку)
        """
        payment_status = self._map_status_for_field(
            customer_info.get('status', ''),
            customer_info.get('payment_system_status', '')
        )
        status_enum_id = self._get_status_enum_id(payment_status)

        update_data = {
            "status_id": 143,  # Статус "Возврат"
            "loss_reason_id": 976851  # Причина "Возврат от Radario"
        }

        custom_fields = []

        # 1. Обновляем статус платежа на "Возврат"
        if status_enum_id:
            custom_fields.append({
                "field_id": 986105,
                "values": [{"enum_id": status_enum_id}]
            })

        # 2. Добавляем дату возврата
        if customer_info.get('refund_date'):
            refund_timestamp = self._convert_to_timestamp(customer_info['refund_date'])
            custom_fields.append({
                "field_id": 986123,
                "values": [{"value": refund_timestamp}]
            })
        else:
            custom_fields.append({
                "field_id": 986123,
                "values": [{"value": int(time.time())}]
            })

        if custom_fields:
            update_data["custom_fields_values"] = custom_fields

        logger.info(f"🔄 Обновляю сделку {lead_id} для возврата")

        try:
            data = self._make_request('PATCH', f'leads/{lead_id}', update_data)
            logger.info(f"✅ Сделка {lead_id} успешно обновлена для возврата")
            return data
        except Exception as e:
            logger.error(f"❌ Ошибка обновления сделки {lead_id} для возврата: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Ответ API: {e.response.text}")
            raise

    def update_lead(self, lead_id, customer_info, status_id=None):
        """
        Обновляет существующую сделку (БЕЗ обновления согласия на рассылку)
        """
        status_value = self._map_status_for_field(
            customer_info['status'],
            customer_info['payment_system_status']
        )
        status_enum_id = self._get_status_enum_id(status_value)

        update_data = {
            "id": lead_id,
            "price": int(float(customer_info['amount'])),
        }

        if status_id:
            update_data["status_id"] = status_id

        custom_fields = []

        # Обновляем статус платежа
        if status_enum_id:
            custom_fields.append({
                "field_id": 986105,
                "values": [{"enum_id": status_enum_id}]
            })

        # Обновляем количество билетов
        if customer_info.get('tickets_count', 0) > 0:
            custom_fields.append({
                "field_id": 986253,
                "values": [{"value": customer_info['tickets_count']}]
            })

        if custom_fields:
            update_data["custom_fields_values"] = custom_fields

        logger.info(f"📝 Обновляю сделку {lead_id}")

        try:
            data = self._make_request('PATCH', f'leads/{lead_id}', update_data)
            logger.info(f"✅ Сделка {lead_id} успешно обновлена")
            return data
        except Exception as e:
            logger.error(f"❌ Ошибка обновления сделки {lead_id}: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Ответ API: {e.response.text}")
            raise

    def _map_status_for_field(self, status, payment_system_status):
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

        if event_type in mapping:
            return mapping[event_type]

        for key, enum_id in mapping.items():
            if key.lower() == event_type.lower():
                return enum_id

        logger.warning(f"Не найден enum_id для типа события: {event_type}, использую 'Мастер-класс'")
        return 985177

    def _get_status_enum_id(self, status):
        mapping = {
            'Оплачен': 985097,
            'Возврат': 985099,
            'В обработке': None,
            'Отменен': None,
            'Неизвестно': None
        }

        status_to_amo = {
            'Оплачен': 'Оплачено',
            'Возврат': 'Возврат',
            'В обработке': 'Оплачено',
            'Отменен': 'Оплачено',
            'Неизвестно': 'Оплачено'
        }

        mapped_status = status_to_amo.get(status, 'Оплачено')
        return mapping.get(mapped_status, 985097)