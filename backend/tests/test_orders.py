import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.dependencies import get_current_user
from app.db.session import get_session
from app.main import app
from app.models import Order, Payment, Product, User

_ADDRESS = {
    "name": "Ada Lovelace",
    "phone": "+14155552671",
    "address_line_1": "1 Analytical Engine Way",
    "city": "London",
    "state": "London",
    "country": "GB",
}


@dataclass
class OrderTestClient:
    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]
    user_id: int
    user: User

    async def add_product(
        self,
        *,
        name: str,
        price_minor: int = 100,
        stock_quantity: int = 10,
        is_active: bool = True,
    ) -> int:
        async with self.session_factory.begin() as session:
            product = Product(
                name=name,
                price_minor=price_minor,
                stock_quantity=stock_quantity,
                is_active=is_active,
            )
            session.add(product)
            await session.flush()
            return product.id

    async def add_products(
        self,
        products: list[Product],
    ) -> list[int]:
        async with self.session_factory.begin() as session:
            session.add_all(products)
            await session.flush()
            return [product.id for product in products]


@pytest_asyncio.fixture
async def order_client(
    test_engine: AsyncEngine,
) -> AsyncIterator[OrderTestClient]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory.begin() as session:
        user = User(
            auth0_sub="auth0|orders-test",
            email="orders-test@example.com",
            first_name="Ada",
            last_name="Lovelace",
            created_at=datetime.now(UTC),
        )
        session.add(user)
        await session.flush()
        user_id = user.id

    user = User(
        id=user_id,
        auth0_sub="auth0|orders-test",
        email="orders-test@example.com",
        first_name="Ada",
        last_name="Lovelace",
        created_at=datetime.now(UTC),
    )

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    async def override_current_user() -> User:
        return user

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_current_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            yield OrderTestClient(client, session_factory, user_id, user)
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_user, None)


async def _stock_quantity(
    session_factory: async_sessionmaker[AsyncSession],
    product_id: int,
) -> int:
    async with session_factory() as session:
        quantity = await session.scalar(
            select(Product.stock_quantity).where(Product.id == product_id)
        )
    assert quantity is not None
    return quantity


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
    items: list[dict[str, int]],
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"items": items, "shipping_address": _ADDRESS}
    if extra:
        payload.update(extra)
    return payload


async def test_product_reads_hide_inactive_products(
    order_client: OrderTestClient,
) -> None:
    active_id = await order_client.add_product(name="Active")
    inactive_id = await order_client.add_product(name="Inactive", is_active=False)

    page = await order_client.client.get("/api/v1/products")
    assert page.status_code == 200
    assert [product["id"] for product in page.json()["items"]] == [active_id]
    assert page.json()["next_cursor"] is None
    assert page.json()["items"][0]["stock_quantity"] == 10

    active = await order_client.client.get(f"/api/v1/products/{active_id}")
    inactive = await order_client.client.get(f"/api/v1/products/{inactive_id}")
    assert active.status_code == 200
    assert inactive.status_code == 404


async def test_create_order_computes_total_snapshots_price_and_reserves_stock(
    order_client: OrderTestClient,
) -> None:
    first_id = await order_client.add_product(
        name="First", price_minor=125, stock_quantity=8
    )
    second_id = await order_client.add_product(
        name="Second", price_minor=250, stock_quantity=4
    )
    response = await order_client.client.post(
        "/api/v1/orders",
        json=_order_payload(
            [
                {"product_id": first_id, "quantity": 2},
                {"product_id": second_id, "quantity": 3},
            ],
            extra={"total_minor": 1, "price_minor": 1},
        ),
    )

    assert response.status_code == 200
    order = response.json()
    assert order["total_minor"] == 1000
    assert order["currency"] == "NGN"
    assert order["status"] == "pending"
    assert order["shipping_address"] == _ADDRESS
    assert order["items"] == [
        {"product_id": first_id, "quantity": 2, "unit_price_minor": 125},
        {"product_id": second_id, "quantity": 3, "unit_price_minor": 250},
    ]
    assert await _stock_quantity(order_client.session_factory, first_id) == 6
    assert await _stock_quantity(order_client.session_factory, second_id) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"items": [], "shipping_address": {"name": "Missing required fields"}},
        {
            "items": [{"product_id": 1, "quantity": 0}],
            "shipping_address": _ADDRESS,
        },
        {
            "items": [
                {"product_id": 1, "quantity": 1},
                {"product_id": 1, "quantity": 2},
            ],
            "shipping_address": _ADDRESS,
        },
        {
            "items": [{"product_id": 1, "quantity": 1}],
            "shipping_address": {**_ADDRESS, "phone": "not-e164"},
        },
        {
            "items": [{"product_id": 1, "quantity": 1}],
            "shipping_address": {**_ADDRESS, "country": "USA"},
        },
    ],
)
async def test_invalid_order_payload_is_rejected(
    order_client: OrderTestClient,
    payload: dict[str, Any],
) -> None:
    response = await order_client.client.post("/api/v1/orders", json=payload)
    assert response.status_code == 422
    assert await _order_count(order_client.session_factory, order_client.user_id) == 0


async def test_missing_or_inactive_products_return_conflict_without_order(
    order_client: OrderTestClient,
) -> None:
    inactive_id = await order_client.add_product(name="Inactive", is_active=False)
    active_id = await order_client.add_product(name="Active", stock_quantity=5)

    response = await order_client.client.post(
        "/api/v1/orders",
        json=_order_payload(
            [
                {"product_id": active_id, "quantity": 2},
                {"product_id": inactive_id, "quantity": 1},
                {"product_id": 99999, "quantity": 1},
            ]
        ),
    )
    assert response.status_code == 409
    assert response.json() == {
        "detail": {"unavailable_product_ids": [inactive_id, 99999]}
    }
    assert await _stock_quantity(order_client.session_factory, active_id) == 5
    assert await _order_count(order_client.session_factory, order_client.user_id) == 0


async def test_insufficient_stock_rolls_back_order_and_all_reservations(
    order_client: OrderTestClient,
) -> None:
    first_id = await order_client.add_product(
        name="First", price_minor=100, stock_quantity=10
    )
    second_id = await order_client.add_product(
        name="Second", price_minor=200, stock_quantity=1
    )
    response = await order_client.client.post(
        "/api/v1/orders",
        json=_order_payload(
            [
                {"product_id": first_id, "quantity": 4},
                {"product_id": second_id, "quantity": 2},
            ]
        ),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": {"unavailable_product_ids": [second_id]}}
    assert await _stock_quantity(order_client.session_factory, first_id) == 10
    assert await _stock_quantity(order_client.session_factory, second_id) == 1
    assert await _order_count(order_client.session_factory, order_client.user_id) == 0


async def test_idempotency_replays_same_order_and_rejects_changed_payload(
    order_client: OrderTestClient,
) -> None:
    product_id = await order_client.add_product(name="Replay", stock_quantity=10)
    headers = {"Idempotency-Key": "replay-1"}
    payload = _order_payload([{"product_id": product_id, "quantity": 2}])

    first = await order_client.client.post(
        "/api/v1/orders", json=payload, headers=headers
    )
    replay = await order_client.client.post(
        "/api/v1/orders", json=payload, headers=headers
    )
    mismatch = await order_client.client.post(
        "/api/v1/orders",
        json=_order_payload([{"product_id": product_id, "quantity": 3}]),
        headers=headers,
    )

    assert first.status_code == replay.status_code == 200
    assert replay.json() == first.json()
    assert mismatch.status_code == 422
    assert mismatch.json() == {"detail": "idempotency_key_reused"}
    assert await _stock_quantity(order_client.session_factory, product_id) == 8
    assert await _order_count(order_client.session_factory, order_client.user_id) == 1


async def test_orders_without_idempotency_key_are_not_deduplicated(
    order_client: OrderTestClient,
) -> None:
    product_id = await order_client.add_product(name="No key", stock_quantity=10)
    payload = _order_payload([{"product_id": product_id, "quantity": 1}])
    first = await order_client.client.post("/api/v1/orders", json=payload)
    second = await order_client.client.post("/api/v1/orders", json=payload)

    assert first.status_code == second.status_code == 200
    assert first.json()["id"] != second.json()["id"]
    assert await _stock_quantity(order_client.session_factory, product_id) == 8
    assert await _order_count(order_client.session_factory, order_client.user_id) == 2


async def test_order_has_no_item_or_quantity_maximum(
    order_client: OrderTestClient,
) -> None:
    products = [
        Product(
            name=f"Uncapped {index}",
            price_minor=100,
            stock_quantity=101,
            is_active=True,
        )
        for index in range(101)
    ]
    product_ids = await order_client.add_products(products)
    response = await order_client.client.post(
        "/api/v1/orders",
        json=_order_payload(
            [
                {"product_id": product_ids[0], "quantity": 101},
                *[
                    {"product_id": product_id, "quantity": 1}
                    for product_id in product_ids[1:]
                ],
            ]
        ),
    )

    assert response.status_code == 200
    assert response.json()["total_minor"] == 20100
    assert len(response.json()["items"]) == 101
    assert await _stock_quantity(order_client.session_factory, product_ids[0]) == 0


async def test_cancel_releases_stock_once_and_is_user_scoped(
    order_client: OrderTestClient,
    test_engine: AsyncEngine,
) -> None:
    product_id = await order_client.add_product(name="Cancel", stock_quantity=5)
    create_response = await order_client.client.post(
        "/api/v1/orders",
        json=_order_payload([{"product_id": product_id, "quantity": 3}]),
    )
    order_id = create_response.json()["id"]
    assert await _stock_quantity(order_client.session_factory, product_id) == 2

    other_user_id = await _insert_other_user(test_engine)
    other_order_id = await _insert_order_for_user(
        order_client.session_factory,
        user_id=other_user_id,
    )
    owner_list = await order_client.client.get("/api/v1/orders")
    assert [order["id"] for order in owner_list.json()["items"]] == [order_id]

    other_user = User(
        id=other_user_id,
        auth0_sub="auth0|other-orders-test",
        email="other-orders-test@example.com",
        first_name="Other",
        last_name=None,
        created_at=datetime.now(UTC),
    )
    app.dependency_overrides[get_current_user] = _fixed_user(other_user)
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
    assert await _stock_quantity(order_client.session_factory, product_id) == 2

    cancelled = await order_client.client.post(f"/api/v1/orders/{order_id}/cancel")
    replay = await order_client.client.post(f"/api/v1/orders/{order_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert replay.status_code == 409
    assert replay.json() == {"detail": "order_not_pending"}
    assert await _stock_quantity(order_client.session_factory, product_id) == 5


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
            total_minor=0,
            currency="NGN",
            shipping_address=_ADDRESS,
            created_at=now,
            updated_at=now,
        )
        session.add(order)
        await session.flush()
        return order.id


def _fixed_user(user: User):
    async def override_current_user() -> User:
        return user

    return override_current_user


async def test_order_detail_exposes_only_safe_payment_fields(
    order_client: OrderTestClient,
) -> None:
    product_id = await order_client.add_product(name="Payment summary")
    created = await order_client.client.post(
        "/api/v1/orders",
        json=_order_payload([{"product_id": product_id, "quantity": 1}]),
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
    product_id = await order_client.add_product(name="Pagination")
    for _ in range(3):
        response = await order_client.client.post(
            "/api/v1/orders",
            json=_order_payload([{"product_id": product_id, "quantity": 1}]),
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


async def test_product_cursor_pagination_has_no_duplicates_or_gaps(
    order_client: OrderTestClient,
) -> None:
    product_ids = [
        await order_client.add_product(name=f"Page {index}") for index in range(3)
    ]
    first_page = await order_client.client.get("/api/v1/products?limit=2")
    second_page = await order_client.client.get(
        "/api/v1/products",
        params={"limit": 2, "cursor": first_page.json()["next_cursor"]},
    )
    ids = [item["id"] for item in first_page.json()["items"]]
    ids.extend(item["id"] for item in second_page.json()["items"])
    assert ids == product_ids
    assert len(ids) == len(set(ids))


async def test_concurrent_orders_cannot_oversell_stock(
    order_client: OrderTestClient,
) -> None:
    product_id = await order_client.add_product(name="Limited stock", stock_quantity=5)
    responses: list[httpx.Response] = []

    async def place_order(index: int) -> None:
        response = await order_client.client.post(
            "/api/v1/orders",
            json=_order_payload([{"product_id": product_id, "quantity": 2}]),
            headers={"Idempotency-Key": f"stock-race-{index}"},
        )
        responses.append(response)

    async with asyncio.TaskGroup() as task_group:
        for index in range(6):
            task_group.create_task(place_order(index))

    assert sum(response.status_code == 200 for response in responses) == 2
    assert sum(response.status_code == 409 for response in responses) == 4
    assert await _stock_quantity(order_client.session_factory, product_id) == 1
    assert await _order_count(order_client.session_factory, order_client.user_id) == 2


async def test_concurrent_same_key_requests_create_one_order_and_reservation(
    order_client: OrderTestClient,
) -> None:
    product_id = await order_client.add_product(name="Key race", stock_quantity=3)
    responses: list[httpx.Response] = []

    async def place_order() -> None:
        response = await order_client.client.post(
            "/api/v1/orders",
            json=_order_payload([{"product_id": product_id, "quantity": 2}]),
            headers={"Idempotency-Key": "same-concurrent-key"},
        )
        responses.append(response)

    async with asyncio.TaskGroup() as task_group:
        task_group.create_task(place_order())
        task_group.create_task(place_order())

    assert all(response.status_code == 200 for response in responses)
    assert responses[0].json() == responses[1].json()
    assert await _stock_quantity(order_client.session_factory, product_id) == 1
    assert await _order_count(order_client.session_factory, order_client.user_id) == 1


async def test_concurrent_cancel_releases_stock_once(
    order_client: OrderTestClient,
) -> None:
    product_id = await order_client.add_product(name="Cancel race", stock_quantity=4)
    created = await order_client.client.post(
        "/api/v1/orders",
        json=_order_payload([{"product_id": product_id, "quantity": 3}]),
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

    assert sum(response.status_code == 200 for response in responses) == 1
    assert sum(response.status_code == 409 for response in responses) == 1
    assert await _stock_quantity(order_client.session_factory, product_id) == 4
