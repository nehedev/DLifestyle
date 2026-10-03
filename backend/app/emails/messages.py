from app.core.config import settings
from app.emails.resend import EmailMessage
from app.models import Order, OrderItem, Payment, ServiceRequest, User

BUSINESS_NAME = "Dami's Lifestyle Services"


def _money(amount_minor: int, currency: str) -> str:
    major, minor = divmod(amount_minor, 100)
    return f"{major:,}.{minor:02d} {currency}"


def _order_lines(order: Order, items: list[OrderItem]) -> str:
    return "\n".join(
        f"- {item.quantity} x {item.name} "
        f"({_money(item.unit_price_minor, order.currency)})"
        for item in items
    )


def _contact_block(order: Order) -> str:
    contact = order.contact
    lines = [
        f"Name: {contact.get('name')}",
        f"Phone: {contact.get('phone')}",
    ]
    address = contact.get("address")
    if address:
        lines.append(f"Address: {address}")
    return "\n".join(lines)


def welcome_message(user: User) -> EmailMessage:
    return EmailMessage(
        email_type="welcome",
        entity_id=user.id,
        recipient=user.email,
        subject=f"Welcome to {BUSINESS_NAME}",
        text=(
            f"Hello {user.first_name}, your {BUSINESS_NAME} account is ready. "
            "Browse the weekly menu and order for pickup or delivery."
        ),
    )


def order_confirmation_message(order: Order, recipient: str) -> EmailMessage:
    return EmailMessage(
        email_type="order_confirmation",
        entity_id=order.id,
        recipient=recipient,
        subject=f"Order {order.id} confirmed",
        text=(
            f"Order {order.id} is confirmed.\n\n"
            f"Fulfillment: {order.fulfillment_type} on {order.fulfillment_date}\n"
            f"Total: {_money(order.total_minor, order.currency)}"
        ),
    )


def new_order_message(
    order: Order,
    items: list[OrderItem],
    customer: User,
) -> EmailMessage:
    return EmailMessage(
        email_type="new_order",
        entity_id=order.id,
        recipient=settings.owner_notification_email,
        subject=f"New paid order {order.id}",
        text=(
            f"Order {order.id} from {customer.first_name} "
            f"({customer.email}) is paid.\n\n"
            f"Fulfillment: {order.fulfillment_type} on {order.fulfillment_date}\n"
            f"Items:\n{_order_lines(order, items)}\n"
            f"Items total: {_money(order.items_total_minor, order.currency)}\n"
            f"Delivery fee: {_money(order.delivery_fee_minor, order.currency)}\n"
            f"Total: {_money(order.total_minor, order.currency)}\n\n"
            f"{_contact_block(order)}\n"
            f"Notes: {order.notes or 'none'}"
        ),
    )


def payment_failed_message(
    payment: Payment,
    order: Order,
    recipient: str,
) -> EmailMessage:
    return EmailMessage(
        email_type="payment_failed",
        entity_id=payment.id,
        recipient=recipient,
        subject=f"Payment attempt {payment.id} failed",
        text=(
            f"Payment attempt {payment.id} for order {order.id} was marked failed. "
            "You may retry payment from your order."
        ),
    )


def order_cancelled_message(order: Order, recipient: str) -> EmailMessage:
    return EmailMessage(
        email_type="order_cancelled",
        entity_id=order.id,
        recipient=recipient,
        subject=f"Order {order.id} cancelled",
        text=(
            f"Order {order.id} has been cancelled.\n\n"
            f"Fulfillment: {order.fulfillment_type} on {order.fulfillment_date}\n"
            f"Total: {_money(order.total_minor, order.currency)}"
        ),
    )


def request_received_message(
    request: ServiceRequest,
    recipient: str,
) -> EmailMessage:
    return EmailMessage(
        email_type="request_received",
        entity_id=request.id,
        recipient=recipient,
        text=(
            f"We received your request #{request.id}. The owner will follow up.\n\n"
            f"Location: {request.location}\n"
            f"Details: {request.details}\n"
            f"Phone: {request.contact_phone}\n"
            f"Preferred date: {request.preferred_date or 'flexible'}"
        ),
        subject=f"We received your request #{request.id}",
    )


def new_service_request_message(
    request: ServiceRequest,
    service_name: str,
    customer: User,
) -> EmailMessage:
    return EmailMessage(
        email_type="new_service_request",
        entity_id=request.id,
        recipient=settings.owner_notification_email,
        subject=f"New service request #{request.id}",
        text=(
            f"Request #{request.id} for {service_name} from "
            f"{customer.first_name} ({customer.email}).\n\n"
            f"Location: {request.location}\n"
            f"Details: {request.details}\n"
            f"Phone: {request.contact_phone}\n"
            f"Preferred date: {request.preferred_date or 'flexible'}"
        ),
    )
