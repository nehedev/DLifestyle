import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models import Order, Payment

logger = logging.getLogger(__name__)


async def cancel_expired_orders_impl(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    enqueue_cancelled_email: Callable[[int], Any],
) -> list[int]:
    cutoff = datetime.now(UTC) - timedelta(
        minutes=settings.pending_order_timeout_minutes
    )
    cancelled_order_ids: list[int] = []

    async with session_factory() as session:
        async with session.begin():
            candidate_ids = list(
                await session.scalars(
                    select(Order.id)
                    .where(
                        Order.status == "pending",
                        Order.created_at <= cutoff,
                    )
                    .order_by(Order.id)
                    .with_for_update(skip_locked=True)
                )
            )
            if not candidate_ids:
                return []

            for order_id in candidate_ids:
                succeeded_payment_exists = exists(
                    select(Payment.id).where(
                        Payment.order_id == order_id,
                        Payment.status == "succeeded",
                    )
                )
                transition = await session.execute(
                    update(Order)
                    .where(
                        Order.id == order_id,
                        Order.status == "pending",
                        Order.created_at <= cutoff,
                        ~succeeded_payment_exists,
                    )
                    .values(
                        status="cancelled",
                        updated_at=datetime.now(UTC),
                    )
                    .returning(Order.id)
                )
                if transition.scalar_one_or_none() == order_id:
                    cancelled_order_ids.append(order_id)

    for order_id in cancelled_order_ids:
        logger.info("order.expired_cancelled")
        enqueue_cancelled_email(order_id)
    return cancelled_order_ids
