import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.emails.messages import (
    new_order_message,
    new_service_request_message,
    order_cancelled_message,
    order_confirmation_message,
    payment_failed_message,
    request_received_message,
    welcome_message,
)
from app.emails.resend import EmailMessage, ResendClient, ResendError
from app.models import Order, OrderItem, Payment, Service, ServiceRequest, User

logger = logging.getLogger(__name__)


async def _deliver(client: ResendClient, message: EmailMessage) -> None:
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


async def send_new_order_email_impl(
    order_id: int,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    client: ResendClient,
) -> None:
    async with session_factory() as session:
        record = (
            await session.execute(
                select(Order, User)
                .join(User, User.id == Order.user_id)
                .where(Order.id == order_id)
            )
        ).one_or_none()
        if record is None:
            return
        order, customer = record
        items = list(
            await session.scalars(
                select(OrderItem)
                .where(OrderItem.order_id == order_id)
                .order_by(OrderItem.menu_item_id)
            )
        )
    await _deliver(client, new_order_message(order, items, customer))


async def send_request_received_email_impl(
    request_id: int,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    client: ResendClient,
) -> None:
    async with session_factory() as session:
        record = (
            await session.execute(
                select(ServiceRequest, User.email)
                .join(User, User.id == ServiceRequest.user_id)
                .where(ServiceRequest.id == request_id)
            )
        ).one_or_none()
    if record is None:
        return
    request, recipient = record
    await _deliver(client, request_received_message(request, recipient))


async def send_new_service_request_email_impl(
    request_id: int,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    client: ResendClient,
) -> None:
    async with session_factory() as session:
        record = (
            await session.execute(
                select(ServiceRequest, User, Service.name)
                .join(User, User.id == ServiceRequest.user_id)
                .join(Service, Service.id == ServiceRequest.service_id)
                .where(ServiceRequest.id == request_id)
            )
        ).one_or_none()
    if record is None:
        return
    request, customer, service_name = record
    await _deliver(client, new_service_request_message(request, service_name, customer))
