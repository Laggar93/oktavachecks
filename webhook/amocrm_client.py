import requests
import logging
from django.conf import settings
from django.core.cache import cache
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AmoCRMClient:
    def __init__(self):
        self.subdomain = settings.AMOCRM_SUBDOMAIN
        self.base_url = f"https://{self.subdomain}.amocrm.ru/api/v4"
        self._ensure_valid_token()
        self.headers = {
            'Authorization': f'Bearer {self.get_access_token()}',
            'Content-Type': 'application/json'
        }

    def _ensure_valid_token(self):
        """Проверяем и обновляем токен если нужно"""
        token_expiry = cache.get('amocrm_token_expiry')
        if not token_expiry or datetime.now() > token_expiry:
            self._refresh_access_token()

    def get_access_token(self):
        """Получаем текущий access token"""
        return cache.get('amocrm_access_token') or settings.AMOCRM_ACCESS_TOKEN

    def _refresh_access_token(self):
        """Обновляем access token используя refresh token"""
        try:
            url = f"https://{self.subdomain}.amocrm.ru/oauth2/access_token"
            data = {
                "client_id": settings.AMOCRM_CLIENT_ID,
                "client_secret": settings.AMOCRM_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": settings.AMOCRM_REFRESH_TOKEN,
                "redirect_uri": "http://oktavachecks.twc1.net/"
            }

            response = requests.post(url, json=data)
            tokens = response.json()

            if 'access_token' in tokens:
                # Сохраняем новые токены в кэш
                cache.set('amocrm_access_token', tokens['access_token'], 60 * 60 * 23)  # 23 часа
                cache.set('amocrm_refresh_token', tokens['refresh_token'], 60 * 60 * 24 * 89)  # 89 дней

                # Время истечения токена (24 часа от сейчас)
                expiry_time = datetime.now() + timedelta(hours=23, minutes=50)
                cache.set('amocrm_token_expiry', expiry_time)

                logger.info("AmoCRM tokens refreshed successfully")
            else:
                logger.error(f"Token refresh failed: {tokens}")

        except Exception as e:
            logger.error(f"Error refreshing AmoCRM token: {e}")

    def _make_request(self, method, endpoint, data=None):
        """Делаем запрос с автоматическим обновлением токена при 401 ошибке"""
        self._ensure_valid_token()

        url = f"{self.base_url}/{endpoint}"
        headers = {
            'Authorization': f'Bearer {self.get_access_token()}',
            'Content-Type': 'application/json'
        }

        try:
            response = requests.request(method, url, headers=headers, json=data, timeout=30)

            # Если токен истек - обновляем и повторяем запрос
            if response.status_code == 401:
                logger.info("Token expired, refreshing...")
                self._refresh_access_token()
                headers['Authorization'] = f'Bearer {self.get_access_token()}'
                response = requests.request(method, url, headers=headers, json=data, timeout=30)

            response.raise_for_status()
            return response.json() if response.content else {}

        except requests.exceptions.RequestException as e:
            logger.error(f"AmoCRM API error: {e}")
            raise

    # Остальные методы остаются без изменений
    def find_contact_by_email(self, email):
        """Поиск контакта по email"""
        try:
            endpoint = f"contacts?query={email}"
            data = self._make_request('GET', endpoint)
            return data['_embedded']['contacts'][0] if data.get('_embedded', {}).get('contacts') else None
        except Exception as e:
            logger.error(f"Error finding contact by email {email}: {e}")
            return None

    def create_contact(self, email, name, phone=None):
        """Создание нового контакта"""
        contact_data = {
            "name": name,
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

    def create_lead(self, contact_id, lead_name, amount):
        """Создание сделки в воронке Музей на этапе Новая заявка"""
        # amount - сумма в рублях (может быть float: 1000.50)
        price = int(round(float(amount) * 100))  # Конвертируем в копейки

        lead_data = {
            "name": lead_name,
            "price": price,  # В копейках
            "pipeline_id": 9713218,  # ID воронки "Музей"
            "status_id": 77419818,  # ID этапа "Новая заявка"
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