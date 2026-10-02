from app.emails.resend import EmailMessage
from app.models import Order, Payment, User


def welcome_message(user: User) -> EmailMessage:
    return EmailMessage(
        email_type="welcome",
        entity_id=user.id,
        recipient=user.email,
        subject="Welcome to Ficmart",
        text=f"Hello {user.first_name}, your Ficmart account is ready.",
    )


def order_confirmation_message(order: Order, recipient: str) -> EmailMessage:
    return EmailMessage(
        email_type="order_confirmation",
        entity_id=order.id,
        recipient=recipient,
        subject=f"Order {order.id} confirmed",
        text=(
            f"Order {order.id} is confirmed. "
            f"Total: {order.total_minor} {order.currency}."
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
        text=f"Order {order.id} has been cancelled.",
    )
