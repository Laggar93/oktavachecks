import requests
import logging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class AmoCRMClient:
    def __init__(self):
        self.subdomain = settings.AMOCRM_SUBDOMAIN
        self.access_token = settings.AMOCRM_ACCESS_TOKEN
        self.base_url = f"https://{self.subdomain}.amocrm.ru/api/v4"
        self.headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

    def _make_request(self, method, endpoint, data=None):
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.request(method, url, headers=self.headers, json=data, timeout=30)
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
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
        """Создание сделки"""
        lead_data = {
            "name": lead_name,
            "price": int(amount * 100),  # Convert to cents/kopeks
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

    def update_contact(self, contact_id, data):
        """Обновление контакта"""
        try:
            endpoint = f"contacts/{contact_id}"
            return self._make_request('PATCH', endpoint, data)
        except Exception as e:
            logger.error(f"Error updating contact {contact_id}: {e}")
            raise