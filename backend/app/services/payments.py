import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Order, Payment, User
from app.payments.protocol import PaymentProvider, PaymentProviderError


class PaymentOrderNotFound(Exception):
    pass


class PaymentOrderNotPending(Exception):
    pass


class PaymentInitializationFailed(Exception):
    pass


async def initialize_payment(
    session: AsyncSession,
    *,
    user: User,
    order_id: int,
    provider: PaymentProvider,
) -> str:
    order = await session.scalar(
        select(Order).where(Order.id == order_id, Order.user_id == user.id)
    )
    if order is None:
        raise PaymentOrderNotFound
    if order.status != "pending":
        raise PaymentOrderNotPending

    reference = str(uuid4())
    now = datetime.now(UTC)
    payment = Payment(
        order_id=order.id,
        provider=provider.name,
        reference=reference,
        provider_transaction_id=None,
        amount_minor=order.total_minor,
        currency=order.currency,
        status="initiated",
        created_at=now,
        updated_at=now,
    )
    session.add(payment)
    await session.commit()

    try:
        initialized = await provider.initialize(
            reference=reference,
            amount_minor=payment.amount_minor,
            currency=payment.currency,
            email=user.email,
            callback_url=settings.payment_callback_url,
        )
    except (PaymentProviderError, httpx.HTTPError, asyncio.TimeoutError) as error:
        raise PaymentInitializationFailed from error
    return initialized.authorization_url
