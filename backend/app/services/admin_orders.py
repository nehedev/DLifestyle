"""Owner order and payment reads and the owner order status flow."""

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cursors import decode_created_cursor, encode_created_cursor
from app.models import Order, OrderItem, Payment
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

ALLOWED_NEXT_STATUS: dict[str, tuple[str, ...]] = {
    "paid": ("preparing", "cancelled"),
    "preparing": ("ready", "cancelled"),
    "ready": ("completed",),
    "pending": (),
    "completed": (),
    "cancelled": (),
}


class OrderNotFound(Exception):
    pass


class IllegalOrderTransition(Exception):
    pass


class OwnerCancelConflict(Exception):
    pass


@dataclass(frozen=True, slots=True)
class AdminOrderDetail:
    order: Order
    items: list[OrderItem]
    payments: list[Payment]


async def _load_detail(
    session: AsyncSession,
    order_id: int,
) -> AdminOrderDetail:
    order = await session.get(Order, order_id)
    if order is None:
        raise OrderNotFound
    items = list(
        await session.scalars(
            select(OrderItem)
            .where(OrderItem.order_id == order_id)
            .order_by(OrderItem.menu_item_id)
        )
    )
    payments = list(
        await session.scalars(
            select(Payment).where(Payment.order_id == order_id).order_by(Payment.id)
        )
    )
    return AdminOrderDetail(order=order, items=items, payments=payments)


async def list_admin_orders(
    session: AsyncSession,
    *,
    status: str | None,
    fulfillment_date: date | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[Order], str | None]:
    statement = select(Order)
    if status is not None:
        statement = statement.where(Order.status == status)
    if fulfillment_date is not None:
        statement = statement.where(Order.fulfillment_date == fulfillment_date)
    if cursor is not None:
        created_at, order_id = decode_created_cursor(cursor)
        statement = statement.where(
            or_(
                Order.created_at < created_at,
                and_(Order.created_at == created_at, Order.id < order_id),
            )
        )
    statement = statement.order_by(Order.created_at.desc(), Order.id.desc()).limit(
        limit + 1
    )
    orders = list(await session.scalars(statement))
    has_next = len(orders) > limit
    page = orders[:limit]
    last_order = page[-1] if page else None
    next_cursor = (
        encode_created_cursor(last_order.created_at, last_order.id)
        if has_next and last_order is not None
        else None
    )
    return page, next_cursor


async def list_admin_payments(
    session: AsyncSession,
    *,
    status: str | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[Payment], str | None]:
    statement = select(Payment)
    if status is not None:
        statement = statement.where(Payment.status == status)
    if cursor is not None:
        created_at, payment_id = decode_created_cursor(cursor)
        statement = statement.where(
            or_(
                Payment.created_at < created_at,
                and_(Payment.created_at == created_at, Payment.id < payment_id),
            )
        )
    statement = statement.order_by(Payment.created_at.desc(), Payment.id.desc()).limit(
        limit + 1
    )
    payments = list(await session.scalars(statement))
    has_next = len(payments) > limit
    page = payments[:limit]
    last_payment = page[-1] if page else None
    next_cursor = (
        encode_created_cursor(last_payment.created_at, last_payment.id)
        if has_next and last_payment is not None
        else None
    )
    return page, next_cursor


async def get_admin_order(
    session: AsyncSession,
    *,
    order_id: int,
) -> AdminOrderDetail:
    return await _load_detail(session, order_id)


async def set_owner_order_status(
    session: AsyncSession,
    *,
    order_id: int,
    new_status: str,
) -> AdminOrderDetail:
    order = await session.scalar(
        select(Order).where(Order.id == order_id).with_for_update()
    )
    if order is None:
        raise OrderNotFound
    if new_status not in ALLOWED_NEXT_STATUS.get(order.status, ()):
        raise IllegalOrderTransition

    if new_status == "cancelled":
        return await _owner_cancel(session, order=order)

    transition = await session.execute(
        update(Order)
        .where(Order.id == order_id, Order.status == order.status)
        .values(status=new_status, updated_at=datetime.now(UTC))
        .returning(Order.id)
    )
    if transition.scalar_one_or_none() != order_id:
        await session.rollback()
        raise IllegalOrderTransition
    await session.commit()
    return await _load_detail(session, order_id)


async def _owner_cancel(
    session: AsyncSession,
    *,
    order: Order,
) -> AdminOrderDetail:
    now = datetime.now(UTC)
    order_transition = await session.execute(
        update(Order)
        .where(Order.id == order.id, Order.status.in_(("paid", "preparing")))
        .values(status="cancelled", updated_at=now)
        .returning(Order.id)
    )
    if order_transition.scalar_one_or_none() != order.id:
        await session.rollback()
        raise OwnerCancelConflict

    succeeded_payment_id = await session.scalar(
        select(Payment.id)
        .where(Payment.order_id == order.id, Payment.status == "succeeded")
        .order_by(Payment.id)
        .limit(1)
    )
    if succeeded_payment_id is None:
        await session.rollback()
        raise OwnerCancelConflict
    payment_transition = await session.execute(
        update(Payment)
        .where(
            Payment.id == succeeded_payment_id,
            Payment.status == "succeeded",
        )
        .values(status="refund_pending", updated_at=now)
        .returning(Payment.id)
    )
    if payment_transition.scalar_one_or_none() != succeeded_payment_id:
        await session.rollback()
        raise OwnerCancelConflict

    await session.commit()
    logger.info("order.owner_cancelled")
    celery_app.send_task("send_order_cancelled_email", args=[order.id])
    celery_app.send_task("refund_payment", args=[succeeded_payment_id])
    return await _load_detail(session, order.id)
