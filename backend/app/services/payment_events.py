import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Order, Payment
from app.payments.protocol import PaymentEvent, PaymentProvider
from app.services.orders import (
    OrderCanNoLongerBeFulfilled,
    UnavailableMenuItems,
    can_still_be_fulfilled,
)
from app.services.store_settings import StoreNotConfigured
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _can_still_be_fulfilled(
    session: AsyncSession,
    *,
    order: Order,
    now: datetime,
) -> bool:
    try:
        await can_still_be_fulfilled(session, order=order)
    except (StoreNotConfigured, OrderCanNoLongerBeFulfilled, UnavailableMenuItems):
        return False
    return True


async def _conditional_payment_transition(
    session: AsyncSession,
    *,
    payment: Payment,
    expected_status: str,
    new_status: str,
    updated_at: datetime,
    provider_transaction_id: str | None = None,
) -> bool:
    values: dict[str, Any] = {"status": new_status, "updated_at": updated_at}
    if provider_transaction_id is not None:
        values["provider_transaction_id"] = provider_transaction_id
    result = await session.execute(
        update(Payment)
        .where(Payment.id == payment.id, Payment.status == expected_status)
        .values(**values)
        .returning(Payment.id)
    )
    return result.scalar_one_or_none() == payment.id


async def _conditional_order_transition(
    session: AsyncSession,
    *,
    order: Order,
    expected_status: str,
    new_status: str,
    updated_at: datetime,
) -> bool:
    result = await session.execute(
        update(Order)
        .where(Order.id == order.id, Order.status == expected_status)
        .values(status=new_status, updated_at=updated_at)
        .returning(Order.id)
    )
    return result.scalar_one_or_none() == order.id


async def process_payment_event_impl(
    event: PaymentEvent,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    provider: PaymentProvider,
    enqueue_refund: Callable[[int], Any],
) -> None:
    event_type = event["event_type"]
    if event_type in {"ignored", "noop", "refund.pending", "refund.processing"}:
        return

    reference = event.get("reference")
    if not reference:
        logger.error("payment.unknown_reference")
        return

    if event_type == "charge.success":
        await _process_charge_success(
            reference,
            session_factory=session_factory,
            provider=provider,
            enqueue_refund=enqueue_refund,
        )
    elif event_type == "payment.failed":
        await _process_payment_failed(reference, session_factory=session_factory)
    elif event_type in {
        "refund.processed",
        "refund.failed",
        "refund.needs-attention",
    }:
        await _process_refund_event(
            reference,
            event_type=event_type,
            session_factory=session_factory,
        )
    else:
        logger.info("webhook.event_ignored")


async def _process_charge_success(
    reference: str,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    provider: PaymentProvider,
    enqueue_refund: Callable[[int], Any],
) -> None:
    async with session_factory() as session:
        payment = await session.scalar(
            select(Payment).where(Payment.reference == reference)
        )
    if payment is None:
        logger.error("payment.unknown_reference")
        return
    if payment.status == "succeeded":
        return
    if payment.status != "initiated":
        logger.error("payment.invalid_transition")
        return

    verified = await provider.verify(reference)
    if (
        verified.status != "success"
        or verified.amount_minor != payment.amount_minor
        or verified.currency != payment.currency
    ):
        now = datetime.now(UTC)
        async with session_factory() as session:
            async with session.begin():
                current_payment = await session.scalar(
                    select(Payment).where(Payment.id == payment.id).with_for_update()
                )
                if current_payment is None:
                    return
                if current_payment.status == "succeeded":
                    return
                if current_payment.status != "initiated":
                    logger.error("payment.invalid_transition")
                    return
                changed = await _conditional_payment_transition(
                    session,
                    payment=current_payment,
                    expected_status="initiated",
                    new_status="needs_review",
                    updated_at=now,
                    provider_transaction_id=verified.provider_transaction_id,
                )
        if changed:
            logger.error("payment.amount_mismatch")
        return

    enqueue_refund_id: int | None = None
    became_paid = False
    late_reinstated = False
    late_refund_pending = False
    duplicate_needs_review = False
    async with session_factory() as session:
        async with session.begin():
            current_payment = await session.scalar(
                select(Payment).where(Payment.id == payment.id).with_for_update()
            )
            if current_payment is None:
                return
            if current_payment.status == "succeeded":
                return
            if current_payment.status != "initiated":
                logger.error("payment.invalid_transition")
                return

            order = await session.scalar(
                select(Order)
                .where(Order.id == current_payment.order_id)
                .with_for_update()
            )
            if order is None:
                raise RuntimeError("Payment references a missing order")

            now = datetime.now(UTC)
            if order.status == "pending":
                if not await _conditional_order_transition(
                    session,
                    order=order,
                    expected_status="pending",
                    new_status="paid",
                    updated_at=now,
                ):
                    return
                if not await _conditional_payment_transition(
                    session,
                    payment=current_payment,
                    expected_status="initiated",
                    new_status="succeeded",
                    updated_at=now,
                    provider_transaction_id=verified.provider_transaction_id,
                ):
                    raise RuntimeError("Payment transition lost after order update")
                became_paid = True
            elif order.status == "cancelled":
                if await _can_still_be_fulfilled(session, order=order, now=now):
                    if not await _conditional_order_transition(
                        session,
                        order=order,
                        expected_status="cancelled",
                        new_status="paid",
                        updated_at=now,
                    ):
                        return
                    if not await _conditional_payment_transition(
                        session,
                        payment=current_payment,
                        expected_status="initiated",
                        new_status="succeeded",
                        updated_at=now,
                        provider_transaction_id=verified.provider_transaction_id,
                    ):
                        raise RuntimeError("Payment transition lost after order update")
                    became_paid = True
                    late_reinstated = True
                elif await _conditional_payment_transition(
                    session,
                    payment=current_payment,
                    expected_status="initiated",
                    new_status="refund_pending",
                    updated_at=now,
                    provider_transaction_id=verified.provider_transaction_id,
                ):
                    enqueue_refund_id = current_payment.id
                    late_refund_pending = True
            else:
                if await _conditional_payment_transition(
                    session,
                    payment=current_payment,
                    expected_status="initiated",
                    new_status="needs_review",
                    updated_at=now,
                    provider_transaction_id=verified.provider_transaction_id,
                ):
                    duplicate_needs_review = True

    if late_reinstated:
        logger.warning("payment.late_reinstated")
    if late_refund_pending:
        logger.error("payment.late_refund_pending")
    if duplicate_needs_review:
        logger.error("payment.duplicate_needs_review")
    if enqueue_refund_id is not None:
        enqueue_refund(enqueue_refund_id)
    if became_paid:
        celery_app.send_task("send_order_confirmation_email", args=[order.id])


async def _process_payment_failed(
    reference: str,
    *,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    changed = False
    cancelled_order_id: int | None = None
    async with session_factory() as session:
        async with session.begin():
            payment = await session.scalar(
                select(Payment).where(Payment.reference == reference).with_for_update()
            )
            if payment is None:
                logger.error("payment.unknown_reference")
                return
            if payment.status != "initiated":
                return
            order = await session.scalar(
                select(Order).where(Order.id == payment.order_id).with_for_update()
            )
            if order is None:
                raise RuntimeError("Payment references a missing order")

            now = datetime.now(UTC)
            changed = await _conditional_payment_transition(
                session,
                payment=payment,
                expected_status="initiated",
                new_status="failed",
                updated_at=now,
            )
            if changed and order.status == "pending":
                if await _conditional_order_transition(
                    session,
                    order=order,
                    expected_status="pending",
                    new_status="cancelled",
                    updated_at=now,
                ):
                    cancelled_order_id = order.id

    if changed:
        celery_app.send_task("send_payment_failed_email", args=[payment.id])
    if cancelled_order_id is not None:
        celery_app.send_task("send_order_cancelled_email", args=[cancelled_order_id])


async def _process_refund_event(
    reference: str,
    *,
    event_type: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        async with session.begin():
            payment = await session.scalar(
                select(Payment).where(Payment.reference == reference).with_for_update()
            )
            if payment is None:
                logger.error("payment.unknown_reference")
                return
            if payment.status == "refunded" and event_type == "refund.processed":
                return
            if payment.status == "needs_review" and event_type in {
                "refund.failed",
                "refund.needs-attention",
            }:
                return
            if payment.status != "refund_pending":
                logger.error("payment.invalid_transition")
                return
            next_status = (
                "refunded" if event_type == "refund.processed" else "needs_review"
            )
            changed = await _conditional_payment_transition(
                session,
                payment=payment,
                expected_status="refund_pending",
                new_status=next_status,
                updated_at=datetime.now(UTC),
            )
    if changed and event_type != "refund.processed":
        logger.error("payment.refund_failed")


async def refund_payment_impl(
    payment_id: int,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    provider: PaymentProvider,
) -> None:
    async with session_factory() as session:
        payment = await session.scalar(
            select(Payment).where(
                Payment.id == payment_id,
                Payment.status == "refund_pending",
            )
        )
    if payment is None:
        return
    await provider.refund(
        reference=payment.reference,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
    )
