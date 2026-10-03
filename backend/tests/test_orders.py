import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.dependencies import CurrentUser, get_current_user
from app.core.config import settings
from app.db.session import get_session
from app.main import app
from app.models import MenuItem, MenuItemDay, Order, OrderItem, Payment, User
from app.workers.celery_app import celery_app

BUSINESS_ZONE = ZoneInfo(settings.business_timezone)
DELIVERY_FEE_MINOR = 1500
MAX_ADVANCE_DAYS = 7
CUTOFF = time(16, 0)


def business_today() -> date:
    return datetime.now(UTC).astimezone(BUSINESS_ZONE).date()


def a_served_day(offset: int = 1) -> date:
    return business_today() + timedelta(days=offset)


CONTACT = {
    "name": "Ada Obi",
    "phone": "+2348012345678",
    "address": "12 Example Street, Lekki",
}
PICKUP_CONTACT = {"name": "Ada Obi", "phone": "+2348012345678"}


@dataclass
class OrderTestClient:
    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]
    user_id: int
    user: User
    enqueued_tasks: list[tuple[str, list[int] | None]] = field(default_factory=list)

    async def configure_store(
        self,
        *,
        delivery_fee_minor: int = DELIVERY_FEE_MINOR,
        cutoff: time = CUTOFF,
        max_advance_days: int = MAX_ADVANCE_DAYS,
    ) -> None:
        async with self.session_factory.begin() as session:
            from app.models import StoreSettings

            session.add(
                StoreSettings(
                    id=1,
                    delivery_fee_minor=delivery_fee_minor,
                    order_cutoff_time=cutoff,
                    max_advance_days=max_advance_days,
                    updated_at=datetime.now(UTC),
                )
            )

    async def add_menu_item(
        self,
        *,
        name: str = "Jollof rice + chicken",
        price_minor: int = 350_000,
        weekdays: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7),
        is_active: bool = True,
        is_sold_out: bool = False,
    ) -> int:
        async with self.session_factory.begin() as session:
            now = datetime.now(UTC)
            menu_item = MenuItem(
                name=name,
                price_minor=price_minor,
                is_active=is_active,
                is_sold_out=is_sold_out,
                created_at=now,
                updated_at=now,
            )
            session.add(menu_item)
            await session.flush()
            session.add_all(
                MenuItemDay(menu_item_id=menu_item.id, weekday=weekday)
                for weekday in weekdays
            )
            return menu_item.id


@pytest_asyncio.fixture
async def order_client(
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[OrderTestClient]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory.begin() as session:
        user = User(
            auth0_sub="auth0|orders-test",
            email="orders-test@example.com",
            first_name="Ada",
            last_name="Obi",
            created_at=datetime.now(UTC),
        )
        session.add(user)
        await session.flush()
        user_id = user.id

    detached_user = User(
        id=user_id,
        auth0_sub="auth0|orders-test",
        email="orders-test@example.com",
        first_name="Ada",
        last_name="Obi",
        created_at=datetime.now(UTC),
    )
    enqueued_tasks: list[tuple[str, list[int] | None]] = []

    def capture_task(task_name: str, args: list[int] | None = None, **_: Any) -> None:
        enqueued_tasks.append((task_name, args))

    monkeypatch.setattr(celery_app, "send_task", capture_task)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    async def override_current_user() -> CurrentUser:
        return CurrentUser(user=detached_user, roles=frozenset())

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_current_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            yield OrderTestClient(
                client,
                session_factory,
                user_id,
                detached_user,
                enqueued_tasks,
            )
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_user, None)


async def _order_count(
    session_factory: async_sessionmaker[AsyncSession],
    user_id: int,
) -> int:
    async with session_factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(Order).where(Order.user_id == user_id)
        )
    assert count is not None
    return count


def _order_payload(
    menu_item_ids: list[int],
    *,
    fulfillment_type: str = "delivery",
    fulfillment_date: date | None = None,
    contact: dict[str, Any] | None = None,
    notes: str | None = None,
    quantities: list[int] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    quantities = quantities or [1] * len(menu_item_ids)
    payload: dict[str, Any] = {
        "items": [
            {"menu_item_id": menu_item_id, "quantity": quantity}
            for menu_item_id, quantity in zip(menu_item_ids, quantities, strict=True)
        ],
        "fulfillment_type": fulfillment_type,
        "fulfillment_date": (fulfillment_date or a_served_day()).isoformat(),
        "contact": contact if contact is not None else dict(CONTACT),
        "notes": notes,
    }
    if extra:
        payload.update(extra)
    return payload


async def test_store_not_configured_returns_503(
    order_client: OrderTestClient,
) -> None:
    menu_item_id = await order_client.add_menu_item()
    response = await order_client.client.post(
        "/api/v1/orders", json=_order_payload([menu_item_id])
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "store_not_configured"}
    assert await _order_count(order_client.session_factory, order_client.user_id) == 0


async def test_delivery_totals_add_the_flat_fee_and_snapshot_names_and_prices(
    order_client: OrderTestClient,
) -> None:
    await order_client.configure_store()
    first_id = await order_client.add_menu_item(
        name="Jollof rice + chicken", price_minor=350_000
    )
    second_id = await order_client.add_menu_item(
        name="Assorted moi moi", price_minor=150_000
    )

    response = await order_client.client.post(
        "/api/v1/orders",
        json=_order_payload(
            [first_id, second_id],
            quantities=[2, 3],
            extra={"total_minor": 1, "items_total_minor": 1, "delivery_fee_minor": 0},
        ),
    )

    assert response.status_code == 200
    order = response.json()
    assert order["items_total_minor"] == 1_150_000
    assert order["delivery_fee_minor"] == DELIVERY_FEE_MINOR
    assert order["total_minor"] == 1_150_000 + DELIVERY_FEE_MINOR
    assert order["currency"] == "NGN"
    assert order["status"] == "pending"
    assert order["fulfillment_type"] == "delivery"
    assert order["fulfillment_date"] == a_served_day().isoformat()
    assert order["contact"] == CONTACT
    assert order["items"] == [
        {"name": "Jollof rice + chicken", "quantity": 2, "unit_price_minor": 350_000},
        {"name": "Assorted moi moi", "quantity": 3, "unit_price_minor": 150_000},
    ]


async def test_pickup_has_no_delivery_fee(
    order_client: OrderTestClient,
) -> None:
    await order_client.configure_store()
    menu_item_id = await order_client.add_menu_item(price_minor=200_000)
    response = await order_client.client.post(
        "/api/v1/orders",
        json=_order_payload(
            [menu_item_id],
            fulfillment_type="pickup",
            contact=dict(PICKUP_CONTACT),
        ),
    )
    assert response.status_code == 200
    order = response.json()
    assert order["delivery_fee_minor"] == 0
    assert order["total_minor"] == order["items_total_minor"] == 200_000
    assert order["contact"]["address"] is None


async def test_snapshots_survive_a_menu_price_and_name_edit(
    order_client: OrderTestClient,
) -> None:
    await order_client.configure_store()
    menu_item_id = await order_client.add_menu_item(
        name="Original name", price_minor=100_000
    )
    created = await order_client.client.post(
        "/api/v1/orders", json=_order_payload([menu_item_id], quantities=[2])
    )
    order_id = created.json()["id"]

    async with order_client.session_factory.begin() as session:
        menu_item = await session.get(MenuItem, menu_item_id)
        assert menu_item is not None
        menu_item.name = "Renamed dish"
        menu_item.price_minor = 500_000

    detail = await order_client.client.get(f"/api/v1/orders/{order_id}")
    assert detail.status_code == 200
    assert detail.json()["items"] == [
        {"name": "Original name", "quantity": 2, "unit_price_minor": 100_000}
    ]
    assert detail.json()["total_minor"] == 200_000 + DELIVERY_FEE_MINOR


@pytest.mark.parametrize(
    "payload",
    [
        {"items": [], "fulfillment_type": "delivery"},
        {
            "items": [{"menu_item_id": 1, "quantity": 0}],
            "fulfillment_type": "delivery",
            "fulfillment_date": "2026-10-05",
            "contact": CONTACT,
        },
        {
            "items": [
                {"menu_item_id": 1, "quantity": 1},
                {"menu_item_id": 1, "quantity": 2},
            ],
            "fulfillment_type": "delivery",
            "fulfillment_date": "2026-10-05",
            "contact": CONTACT,
        },
        {
            "items": [{"menu_item_id": 1, "quantity": 1}],
            "fulfillment_type": "delivery",
            "fulfillment_date": "2026-10-05",
            "contact": {**CONTACT, "phone": "08012345678"},
        },
        {
            "items": [{"menu_item_id": 1, "quantity": 1}],
            "fulfillment_type": "delivery",
            "fulfillment_date": "2026-10-05",
            "contact": {"name": "Ada Obi", "phone": "+2348012345678"},
        },
        {
            "items": [{"menu_item_id": 1, "quantity": 1}],
            "fulfillment_type": "courier",
            "fulfillment_date": "2026-10-05",
            "contact": CONTACT,
        },
        {
            "items": [{"menu_item_id": 1, "quantity": 1}],
            "fulfillment_type": "delivery",
            "fulfillment_date": "not-a-date",
            "contact": CONTACT,
        },
        {
            "items": [{"menu_item_id": 1, "quantity": 1}],
            "fulfillment_type": "delivery",
            "fulfillment_date": "2026-10-05",
            "contact": CONTACT,
            "notes": "x" * 1001,
        },
    ],
)
async def test_invalid_order_payload_is_rejected(
    order_client: OrderTestClient,
    payload: dict[str, Any],
) -> None:
    await order_client.configure_store()
    response = await order_client.client.post("/api/v1/orders", json=payload)
    assert response.status_code == 422
    assert await _order_count(order_client.session_factory, order_client.user_id) == 0


async def test_blank_contact_strings_are_rejected(
    order_client: OrderTestClient,
) -> None:
    await order_client.configure_store()
    menu_item_id = await order_client.add_menu_item()
    response = await order_client.client.post(
        "/api/v1/orders",
        json=_order_payload([menu_item_id], contact={**CONTACT, "name": "   "}),
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "overrides",
    [
        {"is_active": False},
        {"is_sold_out": True},
    ],
)
async def test_unavailable_items_return_conflict_without_an_order(
    order_client: OrderTestClient,
    overrides: dict[str, Any],
) -> None:
    await order_client.configure_store()
    unavailable_id = await order_client.add_menu_item(name="Unavailable", **overrides)

    response = await order_client.client.post(
        "/api/v1/orders",
        json=_order_payload([unavailable_id]),
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": {"unavailable_menu_item_ids": [unavailable_id]}
    }
    assert await _order_count(order_client.session_factory, order_client.user_id) == 0


async def test_unknown_menu_item_returns_conflict(
    order_client: OrderTestClient,
) -> None:
    await order_client.configure_store()
    response = await order_client.client.post(
        "/api/v1/orders", json=_order_payload([999_999])
    )
    assert response.status_code == 409
    assert response.json() == {"detail": {"unavailable_menu_item_ids": [999_999]}}


async def test_item_not_served_on_the_fulfillment_weekday_is_rejected(
    order_client: OrderTestClient,
) -> None:
    await order_client.configure_store(max_advance_days=14)
    monday_only_id = await order_client.add_menu_item(name="Monday only", weekdays=(1,))
    target = next(
        a_served_day(offset)
        for offset in range(1, 15)
        if a_served_day(offset).isoweekday() != 1
    )
    response = await order_client.client.post(
        "/api/v1/orders",
        json=_order_payload([monday_only_id], fulfillment_date=target),
    )
    assert response.status_code == 409
    assert response.json() == {
        "detail": {"unavailable_menu_item_ids": [monday_only_id]}
    }


async def test_sunday_is_rejected_because_no_item_is_served_then(
    order_client: OrderTestClient,
) -> None:
    await order_client.configure_store(max_advance_days=21)
    saturday_id = await order_client.add_menu_item(name="Sat only", weekdays=(6,))
    sunday = next(
        a_served_day(offset)
        for offset in range(1, 22)
        if a_served_day(offset).isoweekday() == 7
    )
    response = await order_client.client.post(
        "/api/v1/orders",
        json=_order_payload([saturday_id], fulfillment_date=sunday),
    )
    assert response.status_code == 409
    assert response.json() == {"detail": {"unavailable_menu_item_ids": [saturday_id]}}


@pytest.mark.parametrize(
    "payload_change",
    [
        {"quantities": [3]},
        {"fulfillment_type": "pickup", "contact": dict(PICKUP_CONTACT)},
        {"notes": "different notes"},
        {"contact": {**CONTACT, "name": "Someone Else"}},
        {"contact": {**CONTACT, "address": "9 Other Road"}},
        {"contact": {**CONTACT, "phone": "+2348099999999"}},
    ],
)
async def test_idempotency_replays_same_order_and_rejects_changed_payload(
    order_client: OrderTestClient,
    payload_change: dict[str, Any],
) -> None:
    await order_client.configure_store()
    menu_item_id = await order_client.add_menu_item(price_minor=100_000)
    headers = {"Idempotency-Key": "replay-1"}
    payload = _order_payload([menu_item_id], quantities=[2])

    first = await order_client.client.post(
        "/api/v1/orders", json=payload, headers=headers
    )
    replay = await order_client.client.post(
        "/api/v1/orders", json=payload, headers=headers
    )
    changed = _order_payload(
        [menu_item_id],
        quantities=payload_change.pop("quantities", [2]),
    )
    changed["fulfillment_date"] = payload["fulfillment_date"]
    changed.update(payload_change)
    mismatch = await order_client.client.post(
        "/api/v1/orders", json=changed, headers=headers
    )

    assert first.status_code == replay.status_code == 200
    assert replay.json() == first.json()
    assert mismatch.status_code == 422
    assert mismatch.json() == {"detail": "idempotency_key_reused"}
    assert await _order_count(order_client.session_factory, order_client.user_id) == 1


async def test_idempotency_rejects_a_different_fulfillment_date(
    order_client: OrderTestClient,
) -> None:
    await order_client.configure_store()
    menu_item_id = await order_client.add_menu_item()
    headers = {"Idempotency-Key": "date-change"}
    first = await order_client.client.post(
        "/api/v1/orders",
        json=_order_payload([menu_item_id], fulfillment_date=a_served_day(1)),
        headers=headers,
    )
    second = await order_client.client.post(
        "/api/v1/orders",
        json=_order_payload([menu_item_id], fulfillment_date=a_served_day(2)),
        headers=headers,
    )
    assert first.status_code == 200
    assert second.status_code == 422


async def test_orders_without_idempotency_key_are_not_deduplicated(
    order_client: OrderTestClient,
) -> None:
    await order_client.configure_store()
    menu_item_id = await order_client.add_menu_item()
    payload = _order_payload([menu_item_id])
    first = await order_client.client.post("/api/v1/orders", json=payload)
    second = await order_client.client.post("/api/v1/orders", json=payload)

    assert first.status_code == second.status_code == 200
    assert first.json()["id"] != second.json()["id"]
    assert await _order_count(order_client.session_factory, order_client.user_id) == 2


async def test_idempotency_key_length_is_bounded(
    order_client: OrderTestClient,
) -> None:
    await order_client.configure_store()
    menu_item_id = await order_client.add_menu_item()
    response = await order_client.client.post(
        "/api/v1/orders",
        json=_order_payload([menu_item_id]),
        headers={"Idempotency-Key": "x" * 256},
    )
    assert response.status_code == 422


async def test_order_has_no_item_or_quantity_maximum(
    order_client: OrderTestClient,
) -> None:
    await order_client.configure_store()
    first_id = await order_client.add_menu_item(name="Uncapped", price_minor=10_000)
    extra_ids = [
        await order_client.add_menu_item(name=f"Extra {index}", price_minor=10_000)
        for index in range(100)
    ]
    menu_item_ids = [first_id, *extra_ids]
    quantities = [101, *[1] * len(extra_ids)]
    response = await order_client.client.post(
        "/api/v1/orders",
        json=_order_payload(menu_item_ids, quantities=quantities),
    )

    assert response.status_code == 200
    assert response.json()["items_total_minor"] == 2_010_000
    assert len(response.json()["items"]) == 101
    assert response.json()["items"][0]["quantity"] == 101


async def test_cancel_is_user_scoped_and_cancels_once(
    order_client: OrderTestClient,
    test_engine: AsyncEngine,
) -> None:
    await order_client.configure_store()
    menu_item_id = await order_client.add_menu_item()
    created = await order_client.client.post(
        "/api/v1/orders", json=_order_payload([menu_item_id])
    )
    order_id = created.json()["id"]

    other_user_id = await _insert_other_user(test_engine)
    other_order_id = await _insert_order_for_user(
        order_client.session_factory, user_id=other_user_id
    )
    owner_list = await order_client.client.get("/api/v1/orders")
    assert [order["id"] for order in owner_list.json()["items"]] == [order_id]

    app.dependency_overrides[get_current_user] = _fixed_user(
        User(
            id=other_user_id,
            auth0_sub="auth0|other-orders-test",
            email="other-orders-test@example.com",
            first_name="Other",
            last_name=None,
            created_at=datetime.now(UTC),
        )
    )
    try:
        hidden_order = await order_client.client.get(f"/api/v1/orders/{order_id}")
        hidden_cancel = await order_client.client.post(
            f"/api/v1/orders/{order_id}/cancel"
        )
        other_list = await order_client.client.get("/api/v1/orders")
    finally:
        app.dependency_overrides[get_current_user] = _fixed_user(order_client.user)

    assert hidden_order.status_code == 404
    assert hidden_cancel.status_code == 404
    assert [order["id"] for order in other_list.json()["items"]] == [other_order_id]

    cancelled = await order_client.client.post(f"/api/v1/orders/{order_id}/cancel")
    replay = await order_client.client.post(f"/api/v1/orders/{order_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert order_client.enqueued_tasks == [("send_order_cancelled_email", [order_id])]
    assert replay.status_code == 409
    assert replay.json() == {"detail": "order_not_pending"}


async def _insert_other_user(test_engine: AsyncEngine) -> int:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory.begin() as session:
        session.add(
            user := User(
                auth0_sub="auth0|other-orders-test",
                email="other-orders-test@example.com",
                first_name="Other",
                last_name=None,
                created_at=datetime.now(UTC),
            )
        )
        await session.flush()
        return user.id


async def _insert_order_for_user(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    user_id: int,
) -> int:
    now = datetime.now(UTC)
    async with session_factory.begin() as session:
        order = Order(
            user_id=user_id,
            status="pending",
            fulfillment_type="pickup",
            fulfillment_date=a_served_day(),
            contact=dict(PICKUP_CONTACT),
            items_total_minor=0,
            delivery_fee_minor=0,
            total_minor=0,
            currency="NGN",
            created_at=now,
            updated_at=now,
        )
        session.add(order)
        await session.flush()
        return order.id


def _fixed_user(user: User):
    async def override_current_user() -> CurrentUser:
        return CurrentUser(user=user, roles=frozenset())

    return override_current_user


async def test_order_detail_exposes_only_safe_payment_fields(
    order_client: OrderTestClient,
) -> None:
    await order_client.configure_store()
    menu_item_id = await order_client.add_menu_item()
    created = await order_client.client.post(
        "/api/v1/orders", json=_order_payload([menu_item_id])
    )
    order_id = created.json()["id"]
    async with order_client.session_factory.begin() as session:
        session.add(
            Payment(
                order_id=order_id,
                provider="paystack",
                reference="internal-reference",
                provider_transaction_id="internal-transaction",
                amount_minor=100,
                currency="NGN",
                status="initiated",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
    response = await order_client.client.get(f"/api/v1/orders/{order_id}")
    assert response.status_code == 200
    assert set(response.json()["payments"][0]) == {
        "id",
        "status",
        "amount_minor",
        "currency",
    }
    assert "reference" not in response.text
    assert "provider_transaction_id" not in response.text


async def test_order_cursor_pagination_is_stable_and_invalid_cursor_is_400(
    order_client: OrderTestClient,
) -> None:
    await order_client.configure_store()
    menu_item_id = await order_client.add_menu_item()
    for _ in range(3):
        response = await order_client.client.post(
            "/api/v1/orders", json=_order_payload([menu_item_id])
        )
        assert response.status_code == 200

    first_page = await order_client.client.get("/api/v1/orders?limit=2")
    cursor = first_page.json()["next_cursor"]
    second_page = await order_client.client.get(
        "/api/v1/orders", params={"limit": 2, "cursor": cursor}
    )
    all_ids = [order["id"] for order in first_page.json()["items"]]
    all_ids.extend(order["id"] for order in second_page.json()["items"])
    invalid = await order_client.client.get(
        "/api/v1/orders", params={"cursor": "not-a-cursor"}
    )

    assert len(all_ids) == len(set(all_ids)) == 3
    assert second_page.json()["next_cursor"] is None
    assert invalid.status_code == 400
    assert invalid.json() == {"detail": "invalid_cursor"}


async def test_concurrent_same_key_requests_create_one_order(
    order_client: OrderTestClient,
) -> None:
    await order_client.configure_store()
    menu_item_id = await order_client.add_menu_item()
    responses: list[httpx.Response] = []
    payload = _order_payload([menu_item_id], quantities=[2])

    async def place_order() -> None:
        responses.append(
            await order_client.client.post(
                "/api/v1/orders",
                json=payload,
                headers={"Idempotency-Key": "same-concurrent-key"},
            )
        )

    async with asyncio.TaskGroup() as task_group:
        task_group.create_task(place_order())
        task_group.create_task(place_order())

    assert all(response.status_code == 200 for response in responses)
    assert responses[0].json() == responses[1].json()
    assert await _order_count(order_client.session_factory, order_client.user_id) == 1


async def test_concurrent_cancel_cancels_once(
    order_client: OrderTestClient,
) -> None:
    await order_client.configure_store()
    menu_item_id = await order_client.add_menu_item()
    created = await order_client.client.post(
        "/api/v1/orders", json=_order_payload([menu_item_id])
    )
    order_id = created.json()["id"]
    responses: list[httpx.Response] = []

    async def cancel() -> None:
        responses.append(
            await order_client.client.post(f"/api/v1/orders/{order_id}/cancel")
        )

    async with asyncio.TaskGroup() as task_group:
        task_group.create_task(cancel())
        task_group.create_task(cancel())

    assert sorted(response.status_code for response in responses) == [200, 409]
    async with order_client.session_factory() as session:
        order_items = list(await session.scalars(select(OrderItem)))
    assert len(order_items) == 1
