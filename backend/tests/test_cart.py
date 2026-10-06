from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.dependencies import CurrentUser, get_current_user
from app.db.session import get_session
from app.main import app
from app.models import CartItem, MenuItem, Service, User


@dataclass
class CartTestClient:
    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]
    user_id: int


@pytest_asyncio.fixture
async def cart_client(test_engine: AsyncEngine) -> AsyncIterator[CartTestClient]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory.begin() as session:
        user = User(
            provider_sub="google|cart-test",
            email="cart@example.com",
            first_name="Cara",
            last_name=None,
            created_at=datetime.now(UTC),
        )
        session.add(user)
        await session.flush()
        user_id = user.id

    detached_user = User(
        id=user_id,
        provider_sub="google|cart-test",
        email="cart@example.com",
        first_name="Cara",
        last_name=None,
        created_at=datetime.now(UTC),
    )

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    async def override_current_user() -> CurrentUser:
        return CurrentUser(user=detached_user)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_current_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            yield CartTestClient(client, session_factory, user_id)
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_user, None)


async def _add_menu_item(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    name: str = "Jollof rice",
    price_minor: int = 350_000,
) -> int:
    async with session_factory.begin() as session:
        now = datetime.now(UTC)
        menu_item = MenuItem(
            name=name,
            category="Rice",
            price_minor=price_minor,
            is_active=True,
            is_sold_out=False,
            created_at=now,
            updated_at=now,
        )
        menu_item.days = []
        session.add(menu_item)
        await session.flush()
        return menu_item.id


async def _add_service(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    name: str = "Home cleaning",
) -> int:
    async with session_factory.begin() as session:
        now = datetime.now(UTC)
        service = Service(
            name=name,
            description="A spotless home",
            is_active=True,
            sort_order=0,
            created_at=now,
            updated_at=now,
        )
        session.add(service)
        await session.flush()
        return service.id


async def _cart_rows(
    session_factory: async_sessionmaker[AsyncSession],
    user_id: int,
) -> list[CartItem]:
    async with session_factory() as session:
        statement = (
            select(CartItem).where(CartItem.user_id == user_id).order_by(CartItem.id)
        )
        return list(await session.scalars(statement))


async def test_get_cart_starts_empty(cart_client: CartTestClient) -> None:
    response = await cart_client.client.get("/api/v1/cart")
    assert response.status_code == 200
    assert response.json() == {"items": []}


async def test_put_cart_persists_food_and_service(cart_client: CartTestClient) -> None:
    menu_item_id = await _add_menu_item(cart_client.session_factory)
    service_id = await _add_service(cart_client.session_factory)

    response = await cart_client.client.put(
        "/api/v1/cart",
        json={
            "items": [
                {
                    "kind": "food",
                    "menu_item_id": menu_item_id,
                    "quantity": 2,
                },
                {
                    "kind": "service",
                    "service_id": service_id,
                    "quantity": 1,
                    "preferred_date": "2026-11-01",
                },
            ]
        },
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert {(item["kind"], item["quantity"]) for item in items} == {
        ("food", 2),
        ("service", 1),
    }

    reloaded = await cart_client.client.get("/api/v1/cart")
    assert reloaded.json() == response.json()
    assert len(await _cart_rows(cart_client.session_factory, cart_client.user_id)) == 2


async def test_put_cart_replaces_the_previous_snapshot(
    cart_client: CartTestClient,
) -> None:
    first = await _add_menu_item(cart_client.session_factory, name="A")
    second = await _add_menu_item(cart_client.session_factory, name="B")

    await cart_client.client.put(
        "/api/v1/cart",
        json={"items": [{"kind": "food", "menu_item_id": first, "quantity": 1}]},
    )
    response = await cart_client.client.put(
        "/api/v1/cart",
        json={"items": [{"kind": "food", "menu_item_id": second, "quantity": 3}]},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["menu_item_id"] == second
    assert items[0]["quantity"] == 3
    rows = await _cart_rows(cart_client.session_factory, cart_client.user_id)
    assert len(rows) == 1
    assert rows[0].menu_item_id == second


async def test_put_cart_deduplicates_duplicate_lines(
    cart_client: CartTestClient,
) -> None:
    menu_item_id = await _add_menu_item(cart_client.session_factory)

    response = await cart_client.client.put(
        "/api/v1/cart",
        json={
            "items": [
                {"kind": "food", "menu_item_id": menu_item_id, "quantity": 1},
                {"kind": "food", "menu_item_id": menu_item_id, "quantity": 2},
            ]
        },
    )

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1


async def test_put_cart_rejects_an_unknown_menu_item(
    cart_client: CartTestClient,
) -> None:
    response = await cart_client.client.put(
        "/api/v1/cart",
        json={"items": [{"kind": "food", "menu_item_id": 999_999, "quantity": 1}]},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "unknown_cart_item"}
    assert await _cart_rows(cart_client.session_factory, cart_client.user_id) == []


async def test_put_cart_rejects_an_unknown_service(
    cart_client: CartTestClient,
) -> None:
    response = await cart_client.client.put(
        "/api/v1/cart",
        json={"items": [{"kind": "service", "service_id": 999_999, "quantity": 1}]},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "unknown_cart_item"}


async def test_put_cart_rejects_a_malformed_line(cart_client: CartTestClient) -> None:
    menu_item_id = await _add_menu_item(cart_client.session_factory)

    response = await cart_client.client.put(
        "/api/v1/cart",
        json={
            "items": [
                {
                    "kind": "food",
                    "menu_item_id": menu_item_id,
                    "service_id": 5,
                    "quantity": 1,
                }
            ]
        },
    )

    assert response.status_code == 422


async def test_cart_requires_authentication(test_engine: AsyncEngine) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/cart")
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_token"}
