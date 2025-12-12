import json
import logging
from datetime import timezone

logger = logging.getLogger(__name__)


def verify_radario_webhook(payload):
    if 'model' not in payload:
        logger.error(f"No 'model' field in payload: {payload.keys()}")
        return False

    model = payload['model']

    required_fields = ['Id', 'Email', 'Status', 'Event']

    for field in required_fields:
        if field not in model and field.lower() not in model:
            logger.error(f"Missing required field '{field}' in model. Available fields: {list(model.keys())}")
            return False

    return True


def extract_customer_info(webhook_data):
    try:
        model = webhook_data.get('model', {})

        email = model.get('Email', '') or model.get('email', '')
        phone = model.get('User', {}).get('Phone', '') or model.get('user', {}).get('phone', '')

        name = "Клиент Radario"

        tickets = model.get('Tickets', []) or model.get('tickets', [])
        if tickets:
            first_ticket = tickets[0]
            if first_ticket.get('OwnerName'):
                name = first_ticket['OwnerName']
            elif first_ticket.get('participantName'):
                name = first_ticket['participantName']
            elif first_ticket.get('firstName') and first_ticket.get('lastName'):
                name = f"{first_ticket['lastName']} {first_ticket['firstName']}"
            elif first_ticket.get('first_name') and first_ticket.get('last_name'):
                name = f"{first_ticket['last_name']} {first_ticket['first_name']}"

        if name == "Клиент Radario":
            user = model.get('User', {}) or model.get('user', {})
            if user.get('Name'):
                name = user['Name']
            elif user.get('FirstName') and user.get('LastName'):
                name = f"{user['LastName']} {user['FirstName']}"
            elif user.get('firstName') and user.get('lastName'):
                name = f"{user['lastName']} {user['firstName']}"
            elif user.get('first_name') and user.get('last_name'):
                name = f"{user['last_name']} {user['first_name']}"

        if name == "Клиент Radario":
            custom_data = model.get('CustomData') or model.get('customData', '')
            if custom_data and isinstance(custom_data, str):
                try:
                    import json
                    custom_json = json.loads(custom_data)
                    if custom_json.get('name'):
                        name = custom_json['name']
                    elif custom_json.get('fio'):
                        name = custom_json['fio']
                    elif custom_json.get('full_name'):
                        name = custom_json['full_name']
                except:
                    pass

        if name == "Клиент Radario" and email:
            name = email.split('@')[0]
            name = name.capitalize()

        refund_details = model.get('RefundDetails', {}) or model.get('refundDetails', {})
        refund_date = refund_details.get('RefundDate') if refund_details else None

        status = model.get('Status') or model.get('status')
        payment_system_status = model.get('PaymentSystemStatus') or model.get('paymentSystemStatus')

        if (status == 'Refunded' or payment_system_status == 'Refund') and not refund_date:
            refund_date = model.get('UpdateDate') or model.get('updateDate')
            if not refund_date:
                from datetime import datetime
                refund_date = datetime.now().isoformat() + 'Z'

        return {
            'email': email,
            'name': name,
            'phone': phone,
            'order_id': model.get('Id') or model.get('id'),
            'status': model.get('Status') or model.get('status'),
            'payment_system_status': model.get('PaymentSystemStatus') or model.get('paymentSystemStatus'),
            'payment_system_status_description': model.get('PaymentSystemStatusDescription') or model.get('paymentSystemStatusDescription', ''),
            'amount': float(model.get('Amount', 0) or model.get('amount', 0)),
            'host_profit': float(model.get('HostProfit', 0) or model.get('hostProfit', 0)),
            'creation_date': model.get('CreationDate') or model.get('creationDate', ''),
            'payment_date': model.get('PaymentDate') or model.get('paymentDate', ''),
            'update_date': model.get('UpdateDate') or model.get('updateDate', ''),
            'event_title': model.get('Event', {}).get('Title', '') or model.get('event', {}).get('title', ''),
            'event_date': model.get('Event', {}).get('BeginDate', '') or model.get('event', {}).get('beginDate', ''),
            'tickets_count': len(tickets),
            'tickets': tickets,
            'refund_date': refund_date,
            'refund_details': refund_details,
            'payment_type': model.get('PaymentType') or model.get('paymentType', ''),
            'promocode': model.get('Promocode') or model.get('promocode', ''),
            'distribution_type': model.get('DistributionType') or model.get('distributionType', ''),
            'currency': model.get('Currency') or model.get('currency', 'RUB'),
            'utm_data': model.get('UtmData') or model.get('utmData', {}),
            'custom_data': model.get('CustomData') or model.get('customData', ''),
            'source': 'Radario'
        }
    except Exception as e:
        logger.error(f"Error extracting customer info: {e}")
        model = webhook_data.get('model', {})
        return {
            'email': model.get('Email', '') or model.get('email', ''),
            'name': 'Клиент Radario',
            'phone': '',
            'order_id': model.get('Id') or model.get('id'),
            'status': model.get('Status') or model.get('status'),
            'payment_system_status': model.get('PaymentSystemStatus') or model.get('paymentSystemStatus'),
            'amount': float(model.get('Amount', 0) or model.get('amount', 0)),
            'event_title': model.get('Event', {}).get('Title', '') or model.get('event', {}).get('title', ''),
            'tickets_count': 0
        }


def create_lead_name(event_data, order_id):
    event_title = event_data.get('Title') or event_data.get('title', 'Мероприятие')

    if len(event_title) > 100:
        event_title_short = event_title[:97] + "..."
    else:
        event_title_short = event_title

    if order_id:
        return f"Билет на {event_title_short} (#{order_id})"
    else:
        return f"Билет на {event_title_short}"


def should_process_order(webhook_data):
    return True


def format_name_for_amocrm(full_name):
    if not full_name or full_name == "Покупатель билета" or full_name == "Клиент Radario":
        return "Клиент Radario"

    parts = [p.strip() for p in str(full_name).split() if p.strip()]

    if len(parts) == 0:
        return "Клиент Radario"
    elif len(parts) == 1:
        return parts[0]
    elif len(parts) == 2:
        return f"{parts[1]} {parts[0]}"
    elif len(parts) >= 3:
        last_name = parts[0]
        first_initial = parts[1][0] + "." if parts[1] else ""
        middle_initial = parts[2][0] + "." if len(parts) > 2 and parts[2] else ""
        return f"{last_name} {first_initial}{middle_initial}".strip()

    return full_name