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
    """
    Извлекает информацию о клиенте и заказе из вебхука Radario
    """
    try:
        model = webhook_data.get('model', {})

        # Основные поля
        email = model.get('Email', '') or model.get('email', '')
        phone = model.get('User', {}).get('Phone', '') or model.get('user', {}).get('phone', '')

        # ИЗВЛЕЧЕНИЕ СОГЛАСИЯ НА РАССЫЛКУ
        is_agree_ads = False

        if 'isAgreeAds' in model:
            is_agree_ads = model['isAgreeAds']
            logger.info(f"📋 isAgreeAds найден в model: {is_agree_ads} (тип: {type(is_agree_ads)})")

        elif 'user' in model and isinstance(model['user'], dict):
            user_ads = model['user'].get('isAgreeAds', False)
            if user_ads:
                is_agree_ads = user_ads
                logger.info(f"📋 isAgreeAds найден в user: {is_agree_ads}")

        elif 'CustomData' in model and model['CustomData']:
            try:
                custom_data = model['CustomData']
                if isinstance(custom_data, str):
                    custom_json = json.loads(custom_data)
                    if 'isAgreeAds' in custom_json:
                        is_agree_ads = custom_json['isAgreeAds']
                        logger.info(f"📋 isAgreeAds найден в CustomData: {is_agree_ads}")
            except:
                pass

        elif 'Tickets' in model and model['Tickets']:
            for ticket in model['Tickets']:
                if isinstance(ticket, dict) and 'isAgreeAds' in ticket:
                    is_agree_ads = ticket['isAgreeAds']
                    logger.info(f"📋 isAgreeAds найден в Ticket: {is_agree_ads}")
                    break

        if isinstance(is_agree_ads, str):
            is_agree_ads = is_agree_ads.lower() in ['true', '1', 'yes', 'да']

        is_agree_ads = bool(is_agree_ads)

        # Извлечение имени
        name = "Клиент Radario"

        tickets = model.get('Tickets', []) or model.get('tickets', [])
        if tickets and isinstance(tickets, list):
            first_ticket = tickets[0] if tickets else {}
            if isinstance(first_ticket, dict):
                if first_ticket.get('OwnerName'):
                    name = first_ticket['OwnerName']
                elif first_ticket.get('participantName'):
                    name = first_ticket['participantName']
                elif first_ticket.get('firstName') and first_ticket.get('lastName'):
                    name = f"{first_ticket['lastName']} {first_ticket['firstName']}"

        if name == "Клиент Radario":
            user = model.get('User', {}) or model.get('user', {})
            if isinstance(user, dict):
                if user.get('Name'):
                    name = user['Name']
                elif user.get('FirstName') and user.get('LastName'):
                    name = f"{user['LastName']} {user['FirstName']}"

        if name == "Клиент Radario" and email:
            name = email.split('@')[0].capitalize()

        # ИЗВЛЕЧЕНИЕ ТИПА БИЛЕТА
        # Пробуем получить из первого тикета поле TicketType / ticketType / CategoryName
        ticket_type = ''
        if tickets and isinstance(tickets, list):
            first_ticket = tickets[0] if tickets else {}
            if isinstance(first_ticket, dict):
                ticket_type = (
                    first_ticket.get('TicketType')
                    or first_ticket.get('ticketType')
                    or first_ticket.get('CategoryName')
                    or first_ticket.get('categoryName')
                    or first_ticket.get('TypeName')
                    or first_ticket.get('typeName')
                    or ''
                )

        # Если в одном тикете несколько разных типов — собираем уникальные
        if not ticket_type and tickets:
            types = []
            for t in tickets:
                if isinstance(t, dict):
                    t_type = (
                        t.get('TicketType') or t.get('ticketType')
                        or t.get('CategoryName') or t.get('categoryName')
                        or t.get('TypeName') or t.get('typeName')
                    )
                    if t_type and t_type not in types:
                        types.append(t_type)
            ticket_type = ', '.join(types)

        # Извлечение информации о возврате
        refund_details = model.get('RefundDetails', {}) or model.get('refundDetails', {})
        refund_date = None
        if refund_details and isinstance(refund_details, dict):
            refund_date = refund_details.get('RefundDate') or refund_details.get('refundDate')

        status = model.get('Status') or model.get('status')
        payment_system_status = model.get('PaymentSystemStatus') or model.get('paymentSystemStatus')

        if (status == 'Refunded' or payment_system_status == 'Refund') and not refund_date:
            refund_date = model.get('UpdateDate') or model.get('updateDate')

        customer_info = {
            'email': email,
            'name': name,
            'phone': phone,
            'order_id': model.get('Id') or model.get('id'),
            'status': status,
            'payment_system_status': payment_system_status,
            'payment_system_status_description': model.get('PaymentSystemStatusDescription') or model.get('paymentSystemStatusDescription', ''),
            'amount': float(model.get('Amount', 0) or model.get('amount', 0)),
            'host_profit': float(model.get('HostProfit', 0) or model.get('hostProfit', 0)),
            'creation_date': model.get('CreationDate') or model.get('creationDate', ''),
            'payment_date': model.get('PaymentDate') or model.get('paymentDate', ''),
            'update_date': model.get('UpdateDate') or model.get('updateDate', ''),
            'event_title': model.get('Event', {}).get('Title', '') or model.get('event', {}).get('title', ''),
            'event_date': model.get('Event', {}).get('BeginDate', '') or model.get('event', {}).get('beginDate', ''),
            'tickets_count': len(tickets) if tickets else 0,
            'tickets': tickets,
            'ticket_type': ticket_type,  # НОВОЕ ПОЛЕ для воронки Кластер
            'refund_date': refund_date,
            'refund_details': refund_details,
            'payment_type': model.get('PaymentType') or model.get('paymentType', ''),
            'promocode': model.get('Promocode') or model.get('promocode', ''),
            'distribution_type': model.get('DistributionType') or model.get('distributionType', ''),
            'currency': model.get('Currency') or model.get('currency', 'RUB'),
            'utm_data': model.get('UtmData') or model.get('utmData', {}),
            'custom_data': model.get('CustomData') or model.get('customData', ''),
            'source': 'Radario',
            'is_agree_ads': is_agree_ads,
        }

        logger.info(f"📊 Итоговая информация о клиенте: email={email}, is_agree_ads={is_agree_ads}, ticket_type={ticket_type}")
        return customer_info

    except Exception as e:
        logger.error(f"❌ Ошибка в extract_customer_info: {e}", exc_info=True)
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
            'tickets_count': 0,
            'ticket_type': '',
            'is_agree_ads': False,
        }


def create_lead_name(event_data, order_id):
    """Создает название для сделки (старая воронка)"""
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
    """Проверяет, нужно ли обрабатывать заказ"""
    return True


def format_name_for_amocrm(full_name):
    """Форматирует имя для amoCRM"""
    if not full_name or full_name in ("Покупатель билета", "Клиент Radario"):
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