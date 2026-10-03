import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Order, Payment, User
from app.payments.protocol import PaymentProvider, PaymentProviderError
from app.services.orders import (
    OrderCanNoLongerBeFulfilled,
    UnavailableMenuItems,
    can_still_be_fulfilled,
)


class PaymentOrderNotFound(Exception):
    pass


class PaymentOrderNotPending(Exception):
    pass


class PaymentInitializationFailed(Exception):
    pass


class PaymentOrderingClosed(Exception):
    pass


class PaymentItemsUnavailable(Exception):
    def __init__(self, menu_item_ids: list[int]) -> None:
        self.menu_item_ids = menu_item_ids


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
    try:
        await can_still_be_fulfilled(session, order=order)
    except OrderCanNoLongerBeFulfilled as error:
        raise PaymentOrderingClosed from error
    except UnavailableMenuItems as error:
        raise PaymentItemsUnavailable(error.menu_item_ids) from error

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
