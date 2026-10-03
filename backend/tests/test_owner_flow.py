import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, time, timedelta
from typing import Any

import httpx
import pytest
import pytest_asyncio
from conftest import business_today
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.dependencies import CurrentUser, get_current_user
from app.db.session import get_session
from app.main import app
from app.models import (
    MenuItem,
    MenuItemDay,
    Order,
    OrderItem,
    Payment,
    Service,
    ServiceRequest,
    StoreSettings,
    User,
)
from app.workers.celery_app import celery_app


def _now() -> datetime:
    return datetime.now(UTC)


def _in_days(days: int) -> datetime:
    return _now() + timedelta(days=days)


async def _add_user(
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
                first_name="Person",
                last_name=None,
                created_at=_now(),
            )
        )
        await session.flush()
        return user.id


async def _add_service(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    name: str,
    description: str = "A service",
    sort_order: int = 1,
    is_active: bool = True,
) -> int:
    async with session_factory.begin() as session:
        session.add(
            service := Service(
                name=name,
                description=description,
                is_active=is_active,
                sort_order=sort_order,
                created_at=_now(),
                updated_at=_now(),
            )
        )
        await session.flush()
        return service.id


async def _add_order(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    user_id: int,
    status: str = "pending",
    created_at: datetime | None = None,
    fulfillment_date: Any = None,
) -> int:
    created = created_at or _now()
    async with session_factory.begin() as session:
        session.add(
            order := Order(
                user_id=user_id,
                status=status,
                fulfillment_type="pickup",
                fulfillment_date=fulfillment_date
                or (business_today() + timedelta(days=1)),
                contact={"name": "Ada", "phone": "+2348012345678", "address": None},
                items_total_minor=100_000,
                delivery_fee_minor=0,
                total_minor=100_000,
                currency="NGN",
                created_at=created,
                updated_at=created,
            )
        )
        await session.flush()
        session.add(
            OrderItem(
                order_id=order.id,
                menu_item_id=await _add_menu_item(session_factory),
                name="Snap dish",
                quantity=2,
                unit_price_minor=50_000,
            )
        )
        return order.id


async def _add_menu_item(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    name: str = "Snap dish",
    is_active: bool = True,
    is_sold_out: bool = False,
) -> int:
    async with session_factory.begin() as session:
        menu_item = MenuItem(
            name=name,
            category="Rice",
            price_minor=50_000,
            is_active=is_active,
            is_sold_out=is_sold_out,
            created_at=_now(),
            updated_at=_now(),
        )
        menu_item.days = [MenuItemDay(weekday=1)]
        session.add(menu_item)
        await session.flush()
        return menu_item.id


async def _add_payment(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    order_id: int,
    status: str,
    reference: str,
    created_at: datetime | None = None,
) -> int:
    created = created_at or _now()
    async with session_factory.begin() as session:
        session.add(
            payment := Payment(
                order_id=order_id,
                provider="paystack",
                reference=reference,
                provider_transaction_id=(
                    f"txn-{reference}" if status == "succeeded" else None
                ),
                amount_minor=100_000,
                currency="NGN",
                status=status,
                created_at=created,
                updated_at=created,
            )
        )
        await session.flush()
        return payment.id


async def _add_request(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    user_id: int,
    service_id: int,
    status: str = "requested",
    created_at: datetime | None = None,
) -> int:
    created = created_at or _now()
    async with session_factory.begin() as session:
        session.add(
            request := ServiceRequest(
                user_id=user_id,
                service_id=service_id,
                preferred_date=business_today() + timedelta(days=3),
                location="Lekki",
                details="Deep clean the 2 bedroom flat",
                contact_phone="+2348012345678",
                status=status,
                created_at=created,
                updated_at=created,
            )
        )
        await session.flush()
        return request.id


@pytest_asyncio.fixture
async def world(
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[dict[str, Any]]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory.begin() as session:
        session.add(
            StoreSettings(
                id=1,
                delivery_fee_minor=150_000,
                order_cutoff_time=time(23, 59),
                max_advance_days=7,
                updated_at=_now(),
            )
        )

    owner_id = await _add_user(
        session_factory, sub="auth0|owner", email="owner@example.com"
    )
    customer_id = await _add_user(
        session_factory, sub="auth0|customer", email="customer@example.com"
    )
    other_customer_id = await _add_user(
        session_factory, sub="auth0|other", email="other@example.com"
    )
    service_id = await _add_service(session_factory, name="Home cleaning")
    enqueued: list[tuple[str, list[int] | None]] = []

    def capture_task(task_name: str, args: list[int] | None = None, **_: Any) -> None:
        enqueued.append((task_name, args))

    monkeypatch.setattr(celery_app, "send_task", capture_task)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            yield {
                "client": client,
                "sessions": session_factory,
                "owner_id": owner_id,
                "customer_id": customer_id,
                "other_customer_id": other_customer_id,
                "service_id": service_id,
                "enqueued": enqueued,
            }
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_user, None)


def _as(world: dict[str, Any], user_id: int, *, owner: bool = False) -> None:
    user = User(
        id=user_id,
        auth0_sub="stub",
        email="stub@example.com",
        first_name="Stub",
        last_name=None,
        created_at=_now(),
    )

    async def override_get_current_user() -> CurrentUser:
        return CurrentUser(
            user=user, roles=frozenset({"owner"}) if owner else frozenset()
        )

    app.dependency_overrides[get_current_user] = override_get_current_user


def sessions(world: dict[str, Any]) -> async_sessionmaker[AsyncSession]:
    return world["sessions"]


def client(world: dict[str, Any]) -> AsyncClient:
    return world["client"]


def owner(world: dict[str, Any]) -> AsyncClient:
    _as(world, world["owner_id"], owner=True)
    return world["client"]


def customer(world: dict[str, Any], user_id: int | None = None) -> AsyncClient:
    _as(world, user_id if user_id is not None else world["customer_id"])
    return world["client"]


# --- owner order flow -------------------------------------------------------


async def test_owner_lists_orders_with_filters_and_cursor(
    world: dict[str, Any],
) -> None:
    session_factory = sessions(world)
    customer_id = world["customer_id"]
    paid_id = await _add_order(
        session_factory, user_id=customer_id, status="paid", created_at=_now()
    )
    pending_id = await _add_order(
        session_factory,
        user_id=world["other_customer_id"],
        status="pending",
        created_at=_in_days(1),
    )
    session_factory = sessions(world)

    everything = await owner(world).get("/api/v1/admin/orders?limit=1")
    cursor = everything.json()["next_cursor"]
    second_page = await owner(world).get(
        "/api/v1/admin/orders?limit=1", params={"cursor": cursor}
    )
    paid_only = await owner(world).get(
        "/api/v1/admin/orders", params={"status": "paid"}
    )
    fulfillment = await owner(world).get(
        "/api/v1/admin/orders",
        params={"fulfillment_date": (business_today() + timedelta(days=1)).isoformat()},
    )

    ids = [order["id"] for order in everything.json()["items"]]
    ids += [order["id"] for order in second_page.json()["items"]]
    assert sorted(ids) == sorted([paid_id, pending_id])
    assert second_page.json()["next_cursor"] is None
    assert [order["id"] for order in paid_only.json()["items"]] == [paid_id]
    assert len(fulfillment.json()["items"]) == 2
    assert set(everything.json()["items"][0]) == {
        "id",
        "user_id",
        "status",
        "fulfillment_type",
        "fulfillment_date",
        "total_minor",
        "currency",
        "created_at",
    }


async def test_owner_order_detail_exposes_gateway_references(
    world: dict[str, Any],
) -> None:
    session_factory = sessions(world)
    order_id = await _add_order(
        session_factory, user_id=world["customer_id"], status="paid"
    )
    await _add_payment(
        sessions(world), order_id=order_id, status="succeeded", reference="ref-a"
    )
    await _add_payment(
        sessions(world), order_id=order_id, status="initiated", reference="ref-b"
    )

    response = await owner(world).get(f"/api/v1/admin/orders/{order_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == world["customer_id"]
    assert [payment["reference"] for payment in body["payments"]] == ["ref-a", "ref-b"]
    assert set(body["payments"][0]) == {
        "id",
        "reference",
        "provider_transaction_id",
        "status",
        "amount_minor",
        "currency",
    }
    assert body["payments"][0]["provider_transaction_id"] == "txn-ref-a"
    assert body["payments"][1]["provider_transaction_id"] is None
    assert body["items"] == [
        {
            "id": body["items"][0]["id"],
            "menu_item_id": body["items"][0]["menu_item_id"],
            "name": "Snap dish",
            "quantity": 2,
            "unit_price_minor": 50_000,
        }
    ]


async def test_owner_order_detail_of_another_users_order_is_visible(
    world: dict[str, Any],
) -> None:
    order_id = await _add_order(
        sessions(world), user_id=world["other_customer_id"], status="paid"
    )
    response = await owner(world).get(f"/api/v1/admin/orders/{order_id}")
    assert response.status_code == 200
    assert response.json()["user_id"] == world["other_customer_id"]


async def test_owner_order_detail_of_a_missing_order_is_404(
    world: dict[str, Any],
) -> None:
    response = await owner(world).get("/api/v1/admin/orders/9999")
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("start_status", "requested", "expected"),
    [
        ("paid", "preparing", "preparing"),
        ("preparing", "ready", "ready"),
        ("ready", "completed", "completed"),
    ],
)
async def test_owner_moves_an_order_through_the_forward_path(
    world: dict[str, Any],
    start_status: str,
    requested: str,
    expected: str,
) -> None:
    order_id = await _add_order(
        sessions(world), user_id=world["customer_id"], status=start_status
    )

    response = await owner(world).post(
        f"/api/v1/admin/orders/{order_id}/status", json={"status": requested}
    )

    assert response.status_code == 200
    assert response.json()["status"] == expected
    assert world["enqueued"] == []


@pytest.mark.parametrize(
    ("start_status", "requested"),
    [
        ("pending", "preparing"),
        ("pending", "ready"),
        ("pending", "completed"),
        ("pending", "cancelled"),
        ("paid", "ready"),
        ("paid", "completed"),
        ("ready", "preparing"),
        ("ready", "cancelled"),
        ("completed", "cancelled"),
        ("completed", "preparing"),
        ("cancelled", "preparing"),
    ],
)
async def test_owner_rejects_a_transition_outside_the_table(
    world: dict[str, Any],
    start_status: str,
    requested: str,
) -> None:
    order_id = await _add_order(
        sessions(world), user_id=world["customer_id"], status=start_status
    )

    response = await owner(world).post(
        f"/api/v1/admin/orders/{order_id}/status", json={"status": requested}
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "order_transition_not_allowed"}
    async with sessions(world)() as session:
        order = await session.get(Order, order_id)
    assert order is not None
    assert order.status == start_status


async def test_owner_status_body_rejects_an_unknown_status(
    world: dict[str, Any],
) -> None:
    order_id = await _add_order(
        sessions(world), user_id=world["customer_id"], status="paid"
    )
    response = await owner(world).post(
        f"/api/v1/admin/orders/{order_id}/status", json={"status": "shipped"}
    )
    assert response.status_code == 422


async def test_owner_status_on_a_missing_order_is_404(
    world: dict[str, Any],
) -> None:
    response = await owner(world).post(
        "/api/v1/admin/orders/9999/status", json={"status": "preparing"}
    )
    assert response.status_code == 404


async def test_owner_cancel_of_a_paid_order_refunds_atomically(
    world: dict[str, Any],
) -> None:
    order_id = await _add_order(
        sessions(world), user_id=world["customer_id"], status="paid"
    )
    payment_id = await _add_payment(
        sessions(world), order_id=order_id, status="succeeded", reference="ref-paid"
    )
    await _add_payment(
        sessions(world), order_id=order_id, status="initiated", reference="ref-other"
    )

    response = await owner(world).post(
        f"/api/v1/admin/orders/{order_id}/status", json={"status": "cancelled"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    async with sessions(world)() as session:
        order = await session.get(Order, order_id)
        payments = {
            payment.reference: payment.status
            for payment in await session.scalars(
                select(Payment).where(Payment.order_id == order_id)
            )
        }
    assert order is not None
    assert order.status == "cancelled"
    assert payments == {"ref-paid": "refund_pending", "ref-other": "initiated"}
    assert world["enqueued"] == [
        ("send_order_cancelled_email", [order_id]),
        ("refund_payment", [payment_id]),
    ]


async def test_owner_cancel_of_a_preparing_order_also_refunds(
    world: dict[str, Any],
) -> None:
    order_id = await _add_order(
        sessions(world), user_id=world["customer_id"], status="preparing"
    )
    payment_id = await _add_payment(
        sessions(world), order_id=order_id, status="succeeded", reference="ref-paid"
    )

    response = await owner(world).post(
        f"/api/v1/admin/orders/{order_id}/status", json={"status": "cancelled"}
    )

    assert response.status_code == 200
    assert ("refund_payment", [payment_id]) in world["enqueued"]


async def test_owner_cancel_without_a_succeeded_payment_is_409(
    world: dict[str, Any],
) -> None:
    order_id = await _add_order(
        sessions(world), user_id=world["customer_id"], status="paid"
    )

    response = await owner(world).post(
        f"/api/v1/admin/orders/{order_id}/status", json={"status": "cancelled"}
    )

    assert response.status_code == 409
    async with sessions(world)() as session:
        order = await session.get(Order, order_id)
    assert order is not None
    assert order.status == "paid"
    assert world["enqueued"] == []


async def test_concurrent_owner_cancels_refund_once(
    world: dict[str, Any],
) -> None:
    order_id = await _add_order(
        sessions(world), user_id=world["customer_id"], status="paid"
    )
    await _add_payment(
        sessions(world), order_id=order_id, status="succeeded", reference="ref-paid"
    )
    responses: list[httpx.Response] = []

    async def cancel() -> None:
        responses.append(
            await owner(world).post(
                f"/api/v1/admin/orders/{order_id}/status",
                json={"status": "cancelled"},
            )
        )

    async with asyncio.TaskGroup() as task_group:
        task_group.create_task(cancel())
        task_group.create_task(cancel())

    assert sorted(item.status_code for item in responses) == [200, 409]
    refund_tasks = [
        entry for entry in world["enqueued"] if entry[0] == "refund_payment"
    ]
    assert len(refund_tasks) == 1


async def test_admin_order_routes_reject_a_non_owner(world: dict[str, Any]) -> None:
    order_id = await _add_order(
        sessions(world), user_id=world["customer_id"], status="paid"
    )
    orders = await customer(world).get("/api/v1/admin/orders")
    detail = await customer(world).get(f"/api/v1/admin/orders/{order_id}")
    transition = await customer(world).post(
        f"/api/v1/admin/orders/{order_id}/status", json={"status": "preparing"}
    )
    payments = await customer(world).get("/api/v1/admin/payments")

    assert [orders.status_code, detail.status_code, transition.status_code] == [
        403,
        403,
        403,
    ]
    assert payments.status_code == 403


# --- admin payments ---------------------------------------------------------


async def test_admin_payments_filter_by_status_and_paginate(
    world: dict[str, Any],
) -> None:
    order_id = await _add_order(
        sessions(world), user_id=world["customer_id"], status="paid"
    )
    succeeded_id = await _add_payment(
        sessions(world),
        order_id=order_id,
        status="succeeded",
        reference="ref-ok",
        created_at=_now(),
    )
    review_id = await _add_payment(
        sessions(world),
        order_id=order_id,
        status="needs_review",
        reference="ref-review",
        created_at=_in_days(1),
    )
    refund_id = await _add_payment(
        sessions(world),
        order_id=order_id,
        status="refund_pending",
        reference="ref-refund",
        created_at=_in_days(2),
    )

    everything = await owner(world).get("/api/v1/admin/payments?limit=2")
    review = await owner(world).get(
        "/api/v1/admin/payments", params={"status": "needs_review"}
    )
    refunds = await owner(world).get(
        "/api/v1/admin/payments", params={"status": "refund_pending"}
    )

    assert everything.status_code == 200
    assert [payment["id"] for payment in everything.json()["items"]] == [
        refund_id,
        review_id,
    ]
    assert succeeded_id not in [payment["id"] for payment in everything.json()["items"]]
    assert everything.json()["next_cursor"] is not None
    assert [payment["id"] for payment in review.json()["items"]] == [review_id]
    assert len(refunds.json()["items"]) == 1
    assert set(everything.json()["items"][0]) == {
        "id",
        "order_id",
        "reference",
        "provider_transaction_id",
        "status",
        "amount_minor",
        "currency",
        "created_at",
    }


async def test_admin_payments_reject_an_invalid_cursor(
    world: dict[str, Any],
) -> None:
    response = await owner(world).get(
        "/api/v1/admin/payments", params={"cursor": "nope"}
    )
    assert response.status_code == 400


# --- service requests -------------------------------------------------------


async def test_customer_creates_a_service_request(
    world: dict[str, Any],
) -> None:
    request = await customer(world).post(
        "/api/v1/service-requests",
        json={
            "service_id": world["service_id"],
            "preferred_date": (business_today() + timedelta(days=2)).isoformat(),
            "location": "  Lekki  ",
            "details": "Deep clean the 2 bedroom flat",
            "contact_phone": "+2348012345678",
        },
    )

    assert request.status_code == 200
    body = request.json()
    assert body["status"] == "requested"
    assert body["location"] == "Lekki"
    assert body["quoted_amount_minor"] is None
    assert body["owner_note"] is None
    assert world["enqueued"] == [
        ("send_request_received_email", [body["id"]]),
        ("send_new_service_request_email", [body["id"]]),
    ]


async def test_service_request_without_a_preferred_date(
    world: dict[str, Any],
) -> None:
    response = await customer(world).post(
        "/api/v1/service-requests",
        json={
            "service_id": world["service_id"],
            "location": "Lekki",
            "details": "Anything",
            "contact_phone": "+2348012345678",
        },
    )
    assert response.status_code == 200
    assert response.json()["preferred_date"] is None


@pytest.mark.parametrize(
    "body",
    [
        {
            "service_id": 0,
            "location": "Lekki",
            "details": "x",
            "contact_phone": "+2348012345678",
        },
        {
            "service_id": 1,
            "location": "",
            "details": "x",
            "contact_phone": "+2348012345678",
        },
        {
            "service_id": 1,
            "location": "x" * 256,
            "details": "x",
            "contact_phone": "+2348012345678",
        },
        {
            "service_id": 1,
            "location": "Lekki",
            "details": "x" * 2001,
            "contact_phone": "+2348012345678",
        },
        {
            "service_id": 1,
            "location": "Lekki",
            "details": "x",
            "contact_phone": "08012345678",
        },
    ],
)
async def test_service_request_validation(
    world: dict[str, Any],
    body: dict[str, Any],
) -> None:
    response = await customer(world).post("/api/v1/service-requests", json=body)
    assert response.status_code == 422


async def test_service_request_rejects_an_unknown_or_inactive_service(
    world: dict[str, Any],
) -> None:
    inactive_id = await _add_service(
        sessions(world),
        name="Retired",
        sort_order=2,
        is_active=False,
    )
    base = {
        "location": "Lekki",
        "details": "Anything",
        "contact_phone": "+2348012345678",
    }

    unknown = await customer(world).post(
        "/api/v1/service-requests", json={**base, "service_id": 9999}
    )
    inactive = await customer(world).post(
        "/api/v1/service-requests", json={**base, "service_id": inactive_id}
    )

    assert unknown.status_code == 404
    assert inactive.status_code == 409
    assert inactive.json() == {"detail": "service_not_active"}


async def test_service_request_rejects_a_past_preferred_date(
    world: dict[str, Any],
) -> None:
    response = await customer(world).post(
        "/api/v1/service-requests",
        json={
            "service_id": world["service_id"],
            "preferred_date": (business_today() - timedelta(days=1)).isoformat(),
            "location": "Lekki",
            "details": "Anything",
            "contact_phone": "+2348012345678",
        },
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "preferred_date_in_the_past"}


async def test_service_request_today_is_allowed(world: dict[str, Any]) -> None:
    response = await customer(world).post(
        "/api/v1/service-requests",
        json={
            "service_id": world["service_id"],
            "preferred_date": business_today().isoformat(),
            "location": "Lekki",
            "details": "Anything",
            "contact_phone": "+2348012345678",
        },
    )
    assert response.status_code == 200


async def test_customer_sees_only_their_own_service_requests(
    world: dict[str, Any],
) -> None:
    mine_id = await _add_request(
        sessions(world),
        user_id=world["customer_id"],
        service_id=world["service_id"],
        created_at=_now(),
    )
    await _add_request(
        sessions(world),
        user_id=world["other_customer_id"],
        service_id=world["service_id"],
        created_at=_in_days(1),
    )

    listing = await customer(world).get("/api/v1/service-requests")
    detail = await customer(world).get(f"/api/v1/service-requests/{mine_id}")
    hidden = await customer(world).get(f"/api/v1/service-requests/{mine_id + 1}")

    assert [item["id"] for item in listing.json()["items"]] == [mine_id]
    assert detail.status_code == 200
    assert hidden.status_code == 404


async def test_customer_service_request_list_filters_and_paginates(
    world: dict[str, Any],
) -> None:
    for index in range(4):
        await _add_request(
            sessions(world),
            user_id=world["customer_id"],
            service_id=world["service_id"],
            status="requested" if index % 2 == 0 else "contacted",
            created_at=_now() + timedelta(minutes=index),
        )

    requested = await customer(world).get(
        "/api/v1/service-requests", params={"status": "requested"}
    )
    first_page = await customer(world).get("/api/v1/service-requests?limit=2")
    second_page = await customer(world).get(
        "/api/v1/service-requests?limit=2",
        params={"cursor": first_page.json()["next_cursor"]},
    )

    assert len(requested.json()["items"]) == 2
    assert all(item["status"] == "requested" for item in requested.json()["items"])
    ids = [item["id"] for item in first_page.json()["items"]]
    ids += [item["id"] for item in second_page.json()["items"]]
    assert len(ids) == len(set(ids)) == 4
    assert second_page.json()["next_cursor"] is None


@pytest.mark.parametrize(
    "start_status",
    ["requested", "contacted"],
)
async def test_customer_cancels_from_requested_or_contacted(
    world: dict[str, Any],
    start_status: str,
) -> None:
    request_id = await _add_request(
        sessions(world),
        user_id=world["customer_id"],
        service_id=world["service_id"],
        status=start_status,
    )

    response = await customer(world).post(
        f"/api/v1/service-requests/{request_id}/cancel"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


@pytest.mark.parametrize("start_status", ["confirmed", "completed", "cancelled"])
async def test_customer_cannot_cancel_a_later_status(
    world: dict[str, Any],
    start_status: str,
) -> None:
    request_id = await _add_request(
        sessions(world),
        user_id=world["customer_id"],
        service_id=world["service_id"],
        status=start_status,
    )

    response = await customer(world).post(
        f"/api/v1/service-requests/{request_id}/cancel"
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "service_request_not_cancellable"}


async def test_customer_cannot_cancel_another_users_request(
    world: dict[str, Any],
) -> None:
    request_id = await _add_request(
        sessions(world),
        user_id=world["other_customer_id"],
        service_id=world["service_id"],
    )
    response = await customer(world).post(
        f"/api/v1/service-requests/{request_id}/cancel"
    )
    assert response.status_code == 404


async def test_concurrent_customer_cancels_apply_once(
    world: dict[str, Any],
) -> None:
    request_id = await _add_request(
        sessions(world),
        user_id=world["customer_id"],
        service_id=world["service_id"],
    )
    responses: list[httpx.Response] = []

    async def cancel() -> None:
        responses.append(
            await customer(world).post(f"/api/v1/service-requests/{request_id}/cancel")
        )

    async with asyncio.TaskGroup() as task_group:
        task_group.create_task(cancel())
        task_group.create_task(cancel())

    assert sorted(response.status_code for response in responses) == [200, 409]


# --- admin service requests -------------------------------------------------


async def test_admin_service_requests_filter_and_paginate(
    world: dict[str, Any],
) -> None:
    requested_id = await _add_request(
        sessions(world),
        user_id=world["customer_id"],
        service_id=world["service_id"],
        status="requested",
        created_at=_now(),
    )
    await _add_request(
        sessions(world),
        user_id=world["other_customer_id"],
        service_id=world["service_id"],
        status="confirmed",
        created_at=_in_days(1),
    )

    everything = await owner(world).get("/api/v1/admin/service-requests")
    confirmed = await owner(world).get(
        "/api/v1/admin/service-requests", params={"status": "confirmed"}
    )
    detail = await owner(world).get(f"/api/v1/admin/service-requests/{requested_id}")

    assert len(everything.json()["items"]) == 2
    assert len(confirmed.json()["items"]) == 1
    assert detail.status_code == 200
    assert detail.json()["user_id"] == world["customer_id"]


async def test_admin_service_request_detail_of_a_missing_row_is_404(
    world: dict[str, Any],
) -> None:
    response = await owner(world).get("/api/v1/admin/service-requests/9999")
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("start_status", "target", "expected"),
    [
        ("requested", "contacted", "contacted"),
        ("requested", "cancelled", "cancelled"),
        ("contacted", "confirmed", "confirmed"),
        ("contacted", "cancelled", "cancelled"),
        ("confirmed", "completed", "completed"),
        ("confirmed", "cancelled", "cancelled"),
    ],
)
async def test_admin_service_request_transitions(
    world: dict[str, Any],
    start_status: str,
    target: str,
    expected: str,
) -> None:
    request_id = await _add_request(
        sessions(world),
        user_id=world["customer_id"],
        service_id=world["service_id"],
        status=start_status,
    )

    response = await owner(world).patch(
        f"/api/v1/admin/service-requests/{request_id}", json={"status": target}
    )

    assert response.status_code == 200
    assert response.json()["status"] == expected


@pytest.mark.parametrize(
    ("start_status", "target"),
    [
        ("requested", "confirmed"),
        ("requested", "completed"),
        ("contacted", "completed"),
        ("completed", "requested"),
        ("completed", "cancelled"),
        ("cancelled", "requested"),
        ("cancelled", "contacted"),
        ("requested", "requested"),
    ],
)
async def test_admin_rejects_an_illegal_service_request_transition(
    world: dict[str, Any],
    start_status: str,
    target: str,
) -> None:
    request_id = await _add_request(
        sessions(world),
        user_id=world["customer_id"],
        service_id=world["service_id"],
        status=start_status,
    )

    response = await owner(world).patch(
        f"/api/v1/admin/service-requests/{request_id}", json={"status": target}
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "service_request_transition_not_allowed"}
    async with sessions(world)() as session:
        request = await session.get(ServiceRequest, request_id)
    assert request is not None
    assert request.status == start_status


async def test_admin_sets_a_quote_and_an_owner_note(world: dict[str, Any]) -> None:
    request_id = await _add_request(
        sessions(world),
        user_id=world["customer_id"],
        service_id=world["service_id"],
    )

    response = await owner(world).patch(
        f"/api/v1/admin/service-requests/{request_id}",
        json={
            "quoted_amount_minor": 45_000,
            "owner_note": "Quoted by phone",
        },
    )

    assert response.status_code == 200
    assert response.json()["quoted_amount_minor"] == 45_000
    assert response.json()["owner_note"] == "Quoted by phone"
    assert response.json()["status"] == "requested"


async def test_admin_patch_rejects_a_negative_quote_and_unknown_status(
    world: dict[str, Any],
) -> None:
    request_id = await _add_request(
        sessions(world),
        user_id=world["customer_id"],
        service_id=world["service_id"],
    )

    negative = await owner(world).patch(
        f"/api/v1/admin/service-requests/{request_id}",
        json={"quoted_amount_minor": -1},
    )
    unknown = await owner(world).patch(
        f"/api/v1/admin/service-requests/{request_id}", json={"status": "quoted"}
    )

    assert negative.status_code == 422
    assert unknown.status_code == 422


async def test_admin_patch_of_a_missing_service_request_is_404(
    world: dict[str, Any],
) -> None:
    response = await owner(world).patch(
        "/api/v1/admin/service-requests/9999", json={"status": "contacted"}
    )
    assert response.status_code == 404


async def test_admin_service_request_routes_reject_a_non_owner(
    world: dict[str, Any],
) -> None:
    request_id = await _add_request(
        sessions(world),
        user_id=world["customer_id"],
        service_id=world["service_id"],
    )
    listing = await customer(world).get("/api/v1/admin/service-requests")
    detail = await customer(world).get(f"/api/v1/admin/service-requests/{request_id}")
    patched = await customer(world).patch(
        f"/api/v1/admin/service-requests/{request_id}",
        json={"status": "contacted"},
    )

    assert [listing.status_code, detail.status_code, patched.status_code] == [
        403,
        403,
        403,
    ]


async def test_a_deactivated_service_blocks_new_requests_only(
    world: dict[str, Any],
) -> None:
    service_id = world["service_id"]
    existing_id = await _add_request(
        sessions(world),
        user_id=world["customer_id"],
        service_id=service_id,
    )
    async with sessions(world)() as session, session.begin():
        await session.execute(
            update(Service).where(Service.id == service_id).values(is_active=False)
        )

    blocked = await customer(world).post(
        "/api/v1/service-requests",
        json={
            "service_id": service_id,
            "location": "Lekki",
            "details": "Anything",
            "contact_phone": "+2348012345678",
        },
    )
    still_visible = await customer(world).get(f"/api/v1/service-requests/{existing_id}")

    assert blocked.status_code == 409
    assert still_visible.status_code == 200
