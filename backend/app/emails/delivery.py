import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.emails.messages import (
    order_cancelled_message,
    order_confirmation_message,
    payment_failed_message,
    welcome_message,
)
from app.emails.resend import ResendClient, ResendError
from app.models import Order, Payment, User

logger = logging.getLogger(__name__)


async def _deliver(client: ResendClient, message) -> None:
    try:
        await client.send(message)
    except ResendError:
        logger.error("email.send_failed")
        raise


async def send_welcome_email_impl(
    user_id: int,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    client: ResendClient,
) -> None:
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.id == user_id))
    if user is None:
        return
    await _deliver(client, welcome_message(user))


async def send_order_confirmation_email_impl(
    order_id: int,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    client: ResendClient,
) -> None:
    async with session_factory() as session:
        record = (
            await session.execute(
                select(Order, User.email)
                .join(User, User.id == Order.user_id)
                .where(Order.id == order_id)
            )
        ).one_or_none()
    if record is None:
        return
    order, recipient = record
    await _deliver(client, order_confirmation_message(order, recipient))


async def send_payment_failed_email_impl(
    payment_id: int,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    client: ResendClient,
) -> None:
    async with session_factory() as session:
        record = (
            await session.execute(
                select(Payment, Order, User.email)
                .join(Order, Order.id == Payment.order_id)
                .join(User, User.id == Order.user_id)
                .where(Payment.id == payment_id)
            )
        ).one_or_none()
    if record is None:
        return
    payment, order, recipient = record
    await _deliver(client, payment_failed_message(payment, order, recipient))


async def send_order_cancelled_email_impl(
    order_id: int,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    client: ResendClient,
) -> None:
    async with session_factory() as session:
        record = (
            await session.execute(
                select(Order, User.email)
                .join(User, User.id == Order.user_id)
                .where(Order.id == order_id)
            )
        ).one_or_none()
    if record is None:
        return
    order, recipient = record
    await _deliver(client, order_cancelled_message(order, recipient))
