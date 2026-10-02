import asyncio
import logging
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models import MenuItem, Order, OrderItem, Payment, User
from app.services.expiry import cancel_expired_orders_impl
from app.workers.celery_app import celery_app


async def _insert_user(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    sub: str,
    email: str,
) -> int:
    async with session_factory.begin() as session:
        session.add(
            user := User(
                auth0_sub=sub,
                email=email,
                first_name="Expiry",
                last_name=None,
                created_at=datetime.now(UTC),
            )
        )
        await session.flush()
        return user.id


async def _insert_menu_item(
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    async with session_factory.begin() as session:
        now = datetime.now(UTC)
        session.add(
            menu_item := MenuItem(
                name="Expired dish",
                price_minor=100,
                is_active=True,
                is_sold_out=False,
                created_at=now,
                updated_at=now,
            )
        )
        await session.flush()
        return menu_item.id


async def _create_order(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    user_id: int,
    menu_item_id: int,
    created_at: datetime,
    succeeded_payment: bool = False,
) -> int:
    async with session_factory.begin() as session:
        order = Order(
            user_id=user_id,
            status="pending",
            fulfillment_type="pickup",
            fulfillment_date=date(2026, 10, 5),
            contact={"name": "Ada Obi", "phone": "+2348012345678", "address": None},
            items_total_minor=100,
            delivery_fee_minor=0,
            total_minor=100,
            currency="NGN",
            created_at=created_at,
            updated_at=created_at,
        )
        session.add(order)
        await session.flush()
        session.add(
            OrderItem(
                order_id=order.id,
                menu_item_id=menu_item_id,
                name="Expired dish",
                quantity=3,
                unit_price_minor=100,
            )
        )
        if succeeded_payment:
            session.add(
                Payment(
                    order_id=order.id,
                    provider="paystack",
                    reference=f"succeeded-{order.id}",
                    amount_minor=100,
                    currency="NGN",
                    status="succeeded",
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
        return order.id


async def test_expiry_cancels_only_old_unpaid_orders(
    test_engine: AsyncEngine,
    caplog: pytest.LogCaptureFixture,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    user_id = await _insert_user(
        session_factory, sub="auth0|expiry-test", email="expiry-test@example.com"
    )
    menu_item_id = await _insert_menu_item(session_factory)

    now = datetime.now(UTC)
    expiration_cutoff = now - timedelta(minutes=settings.pending_order_timeout_minutes)
    expired_id = await _create_order(
        session_factory,
        user_id=user_id,
        menu_item_id=menu_item_id,
        created_at=expiration_cutoff - timedelta(seconds=1),
    )
    succeeded_id = await _create_order(
        session_factory,
        user_id=user_id,
        menu_item_id=menu_item_id,
        created_at=expiration_cutoff - timedelta(minutes=1),
        succeeded_payment=True,
    )
    recent_id = await _create_order(
        session_factory,
        user_id=user_id,
        menu_item_id=menu_item_id,
        created_at=now,
    )
    enqueued: list[int] = []

    with caplog.at_level(logging.INFO, logger="app.services.expiry"):
        cancelled = await cancel_expired_orders_impl(
            session_factory=session_factory,
            enqueue_cancelled_email=enqueued.append,
        )

    assert cancelled == [expired_id]
    assert enqueued == [expired_id]
    assert "order.expired_cancelled" in caplog.text
    async with session_factory() as session:
        orders = {
            order.id: order.status
            for order in await session.scalars(
                select(Order).where(Order.id.in_([expired_id, succeeded_id, recent_id]))
            )
        }
        items = await session.scalar(
            select(OrderItem).where(OrderItem.order_id == expired_id)
        )
    assert orders == {
        expired_id: "cancelled",
        succeeded_id: "pending",
        recent_id: "pending",
    }
    assert items is not None
    assert items.quantity == 3


async def test_concurrent_expiry_runs_cancel_once(test_engine: AsyncEngine) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    user_id = await _insert_user(
        session_factory, sub="auth0|expiry-race", email="expiry-race@example.com"
    )
    menu_item_id = await _insert_menu_item(session_factory)
    order_id = await _create_order(
        session_factory,
        user_id=user_id,
        menu_item_id=menu_item_id,
        created_at=datetime.now(UTC)
        - timedelta(minutes=settings.pending_order_timeout_minutes + 1),
    )
    queued: list[int] = []
    results: list[list[int]] = []

    async def run_expiry() -> None:
        results.append(
            await cancel_expired_orders_impl(
                session_factory=session_factory,
                enqueue_cancelled_email=queued.append,
            )
        )

    async with asyncio.TaskGroup() as task_group:
        task_group.create_task(run_expiry())
        task_group.create_task(run_expiry())

    assert sum(order_id in result for result in results) == 1
    assert queued == [order_id]
    async with session_factory() as session:
        order = await session.get(Order, order_id)
    assert order is not None
    assert order.status == "cancelled"


def test_expiry_beat_uses_configured_interval() -> None:
    schedule = celery_app.conf.beat_schedule["cancel-expired-orders"]["schedule"]
    assert schedule == timedelta(minutes=settings.expiry_job_interval_minutes)
