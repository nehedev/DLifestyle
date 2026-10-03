import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, time, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.dependencies import CurrentUser, get_current_user
from app.core.config import settings
from app.db.session import get_session
from app.main import app
from app.models import (
    MenuItem,
    MenuItemDay,
    Order,
    OrderItem,
    Service,
    StoreSettings,
    User,
)
from app.services.store_settings import put_store_settings


def _now() -> datetime:
    return datetime.now(UTC)


@pytest_asyncio.fixture
async def admin_session(
    test_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, expire_on_commit=False)


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


async def _add_menu_item(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    name: str,
    price_minor: int = 350_000,
    weekdays: tuple[int, ...] = (1,),
    is_active: bool = True,
    is_sold_out: bool = False,
    description: str | None = None,
) -> int:
    async with session_factory.begin() as session:
        menu_item = MenuItem(
            name=name,
            description=description,
            price_minor=price_minor,
            is_active=is_active,
            is_sold_out=is_sold_out,
            created_at=_now(),
            updated_at=_now(),
        )
        session.add(menu_item)
        await session.flush()
        session.add_all(
            MenuItemDay(menu_item_id=menu_item.id, weekday=weekday)
            for weekday in weekdays
        )
        return menu_item.id


async def _add_service(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    name: str,
    description: str = "A service",
    sort_order: int = 1,
    is_active: bool = True,
) -> int:
    async with session_factory.begin() as session:
        service = Service(
            name=name,
            description=description,
            is_active=is_active,
            sort_order=sort_order,
            created_at=_now(),
            updated_at=_now(),
        )
        session.add(service)
        await session.flush()
        return service.id


def _next_weekday(weekday: int) -> date:
    today = _now().date()
    for offset in range(0, 8):
        candidate = today + timedelta(days=offset)
        if candidate.isoweekday() == weekday:
            return candidate
    raise AssertionError("weekday not reached within a week")


def _session_override(
    session_factory: async_sessionmaker[AsyncSession],
):
    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    return override_get_session


def _owner_override(user: User):
    async def override_get_current_user() -> CurrentUser:
        return CurrentUser(user=user, roles=frozenset({"owner"}))

    return override_get_current_user


def _customer_override(user: User):
    async def override_get_current_user() -> CurrentUser:
        return CurrentUser(user=user, roles=frozenset())

    return override_get_current_user


def _client() -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    )


@pytest_asyncio.fixture
async def owner_client(
    admin_session: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    user_id = await _add_user(
        admin_session, sub="auth0|admin-test", email="owner@example.com"
    )
    owner = User(
        id=user_id,
        auth0_sub="auth0|admin-test",
        email="owner@example.com",
        first_name="Owner",
        last_name=None,
        created_at=_now(),
    )
    app.dependency_overrides[get_session] = _session_override(admin_session)
    app.dependency_overrides[get_current_user] = _owner_override(owner)
    try:
        async with _client() as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def customer_client(
    admin_session: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    user_id = await _add_user(
        admin_session, sub="auth0|customer-test", email="customer@example.com"
    )
    customer = User(
        id=user_id,
        auth0_sub="auth0|customer-test",
        email="customer@example.com",
        first_name="Customer",
        last_name=None,
        created_at=_now(),
    )
    app.dependency_overrides[get_session] = _session_override(admin_session)
    app.dependency_overrides[get_current_user] = _customer_override(customer)
    try:
        async with _client() as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def anonymous_client(
    admin_session: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_session] = _session_override(admin_session)
    try:
        async with _client() as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_user, None)


ADMIN_PATHS = (
    ("GET", "/api/v1/admin/menu-items"),
    ("POST", "/api/v1/admin/menu-items"),
    ("PATCH", "/api/v1/admin/menu-items/1"),
    ("GET", "/api/v1/admin/services"),
    ("POST", "/api/v1/admin/services"),
    ("PATCH", "/api/v1/admin/services/1"),
    ("GET", "/api/v1/admin/store-settings"),
    ("PUT", "/api/v1/admin/store-settings"),
)


@pytest.mark.parametrize(("method", "path"), ADMIN_PATHS)
async def test_admin_endpoints_without_a_token_are_401(
    anonymous_client: AsyncClient,
    method: str,
    path: str,
) -> None:
    response = await anonymous_client.request(method, path, json={})
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_token"}


@pytest.mark.parametrize(("method", "path"), ADMIN_PATHS)
async def test_admin_endpoints_with_a_non_owner_are_403(
    customer_client: AsyncClient,
    method: str,
    path: str,
) -> None:
    response = await customer_client.request(method, path, json={})
    assert response.status_code == 403
    assert response.json() == {"detail": "owner_required"}


async def test_admin_menu_items_list_includes_inactive_and_paginates(
    owner_client: AsyncClient,
    admin_session: async_sessionmaker[AsyncSession],
) -> None:
    first_id = await _add_menu_item(admin_session, name="First dish")
    second_id = await _add_menu_item(admin_session, name="Hidden dish", is_active=False)
    third_id = await _add_menu_item(admin_session, name="Third dish")

    page_one = await owner_client.get("/api/v1/admin/menu-items?limit=2")
    cursor = page_one.json()["next_cursor"]
    page_two = await owner_client.get(
        "/api/v1/admin/menu-items?limit=2", params={"cursor": cursor}
    )
    ids = [item["id"] for item in page_one.json()["items"]]
    ids += [item["id"] for item in page_two.json()["items"]]

    assert sorted(ids) == sorted([first_id, second_id, third_id])
    assert page_two.json()["next_cursor"] is None
    for item in page_one.json()["items"]:
        assert set(item) == {
            "id",
            "name",
            "description",
            "price_minor",
            "is_active",
            "is_sold_out",
            "weekdays",
            "created_at",
            "updated_at",
        }
    by_id = {item["id"]: item for item in page_one.json()["items"]}
    assert by_id[second_id]["is_active"] is False


async def test_admin_menu_item_list_rejects_an_invalid_cursor(
    owner_client: AsyncClient,
) -> None:
    response = await owner_client.get(
        "/api/v1/admin/menu-items", params={"cursor": "not-a-cursor"}
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid_cursor"}


async def test_admin_creates_a_menu_item(
    owner_client: AsyncClient,
    admin_session: async_sessionmaker[AsyncSession],
) -> None:
    response = await owner_client.post(
        "/api/v1/admin/menu-items",
        json={
            "name": "  New dish  ",
            "description": "Tasty",
            "price_minor": 250_000,
            "weekdays": [6, 1, 4],
            "is_sold_out": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "New dish"
    assert body["weekdays"] == [1, 4, 6]
    assert body["is_active"] is True
    assert body["is_sold_out"] is True
    async with admin_session() as session:
        menu_item = await session.get(MenuItem, body["id"])
    assert menu_item is not None
    assert menu_item.name == "New dish"
    assert {day.weekday for day in menu_item.days} == {1, 4, 6}


@pytest.mark.parametrize(
    "body",
    [
        {"name": "", "price_minor": 100, "weekdays": [1]},
        {"name": "   ", "price_minor": 100, "weekdays": [1]},
        {"name": "Dish", "price_minor": -1, "weekdays": [1]},
        {"name": "Dish", "price_minor": 100, "weekdays": []},
        {"name": "Dish", "price_minor": 100, "weekdays": [0]},
        {"name": "Dish", "price_minor": 100, "weekdays": [8]},
        {"name": "Dish", "price_minor": 100},
        {"price_minor": 100, "weekdays": [1]},
    ],
)
async def test_admin_rejects_an_invalid_menu_item(
    owner_client: AsyncClient,
    body: dict[str, object],
) -> None:
    response = await owner_client.post("/api/v1/admin/menu-items", json=body)
    assert response.status_code == 422


async def test_admin_creates_a_zero_price_menu_item(
    owner_client: AsyncClient,
) -> None:
    response = await owner_client.post(
        "/api/v1/admin/menu-items",
        json={"name": "Zero price", "price_minor": 0, "weekdays": [1]},
    )
    assert response.status_code == 200
    assert response.json()["price_minor"] == 0


async def test_admin_patches_a_menu_item_and_its_weekdays(
    owner_client: AsyncClient,
    admin_session: async_sessionmaker[AsyncSession],
) -> None:
    menu_item_id = await _add_menu_item(
        admin_session, name="Old name", weekdays=(1,), price_minor=100_000
    )

    response = await owner_client.patch(
        f"/api/v1/admin/menu-items/{menu_item_id}",
        json={
            "name": "New name",
            "price_minor": 500_000,
            "weekdays": [2, 3],
            "is_sold_out": True,
            "is_active": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "New name"
    assert body["price_minor"] == 500_000
    assert body["weekdays"] == [2, 3]
    assert body["is_sold_out"] is True
    assert body["is_active"] is False


async def test_admin_patch_leaves_omitted_fields_alone(
    owner_client: AsyncClient,
    admin_session: async_sessionmaker[AsyncSession],
) -> None:
    menu_item_id = await _add_menu_item(
        admin_session,
        name="Keep me",
        description="Untouched",
        price_minor=100_000,
        weekdays=(1, 5),
        is_sold_out=True,
    )

    response = await owner_client.patch(
        f"/api/v1/admin/menu-items/{menu_item_id}", json={"price_minor": 1}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Keep me"
    assert body["description"] == "Untouched"
    assert body["price_minor"] == 1
    assert body["weekdays"] == [1, 5]
    assert body["is_sold_out"] is True


async def test_admin_patch_of_a_missing_menu_item_is_404(
    owner_client: AsyncClient,
) -> None:
    response = await owner_client.patch(
        "/api/v1/admin/menu-items/9999", json={"price_minor": 1}
    )
    assert response.status_code == 404


async def test_a_price_edit_leaves_existing_orders_unchanged(
    owner_client: AsyncClient,
    admin_session: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _add_user(
        admin_session, sub="auth0|order-owner", email="order-owner@example.com"
    )
    menu_item_id = await _add_menu_item(
        admin_session, name="Priced dish", price_minor=100_000, weekdays=(1,)
    )
    async with admin_session.begin() as session:
        session.add(
            order := Order(
                user_id=user_id,
                status="pending",
                fulfillment_type="pickup",
                fulfillment_date=_next_weekday(1),
                contact={
                    "name": "Ada",
                    "phone": "+2348012345678",
                    "address": None,
                },
                items_total_minor=200_000,
                delivery_fee_minor=0,
                total_minor=200_000,
                currency="NGN",
                created_at=_now(),
                updated_at=_now(),
            )
        )
        await session.flush()
        session.add(
            OrderItem(
                order_id=order.id,
                menu_item_id=menu_item_id,
                name="Priced dish",
                quantity=2,
                unit_price_minor=100_000,
            )
        )
        order_id = order.id

    patched = await owner_client.patch(
        f"/api/v1/admin/menu-items/{menu_item_id}",
        json={"name": "Repriced dish", "price_minor": 900_000},
    )

    assert patched.status_code == 200
    async with admin_session() as session:
        order = await session.get(Order, order_id)
        items = list(
            await session.scalars(
                select(OrderItem).where(OrderItem.order_id == order_id)
            )
        )
    assert order is not None
    assert order.total_minor == 200_000
    assert [(item.name, item.unit_price_minor) for item in items] == [
        ("Priced dish", 100_000)
    ]


async def test_admin_services_list_and_create(
    owner_client: AsyncClient,
    admin_session: async_sessionmaker[AsyncSession],
) -> None:
    await _add_service(admin_session, name="Home cleaning", sort_order=2)
    await _add_service(admin_session, name="Retired", sort_order=1, is_active=False)

    listing = await owner_client.get("/api/v1/admin/services")
    created = await owner_client.post(
        "/api/v1/admin/services",
        json={"name": "Errand running", "description": "Anything"},
    )

    assert listing.status_code == 200
    assert [item["name"] for item in listing.json()["items"]] == [
        "Retired",
        "Home cleaning",
    ]
    assert created.status_code == 200
    body = created.json()
    assert body["name"] == "Errand running"
    assert body["is_active"] is True
    assert body["sort_order"] == 3
    assert set(body) == {
        "id",
        "name",
        "description",
        "is_active",
        "sort_order",
        "created_at",
        "updated_at",
    }


async def test_admin_creates_a_service_with_an_explicit_sort_order(
    owner_client: AsyncClient,
) -> None:
    response = await owner_client.post(
        "/api/v1/admin/services",
        json={"name": "Home organization", "description": "Tidy up", "sort_order": 0},
    )
    assert response.status_code == 200
    assert response.json()["sort_order"] == 0


async def test_admin_services_list_rejects_an_invalid_cursor(
    owner_client: AsyncClient,
) -> None:
    response = await owner_client.get(
        "/api/v1/admin/services", params={"cursor": "not-a-cursor"}
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid_cursor"}


async def test_admin_patches_a_service(
    owner_client: AsyncClient,
    admin_session: async_sessionmaker[AsyncSession],
) -> None:
    service_id = await _add_service(admin_session, name="Old", sort_order=5)

    response = await owner_client.patch(
        f"/api/v1/admin/services/{service_id}",
        json={"name": "New", "is_active": False, "sort_order": 1},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "New"
    assert response.json()["is_active"] is False
    assert response.json()["sort_order"] == 1
    assert response.json()["description"] == "A service"


async def test_admin_patch_of_a_missing_service_is_404(
    owner_client: AsyncClient,
) -> None:
    response = await owner_client.patch(
        "/api/v1/admin/services/9999", json={"name": "New"}
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"name": "", "description": "x"},
        {"name": "x"},
        {"description": "x"},
    ],
)
async def test_admin_rejects_an_invalid_service(
    owner_client: AsyncClient,
    body: dict[str, object],
) -> None:
    response = await owner_client.post("/api/v1/admin/services", json=body)
    assert response.status_code == 422


async def test_admin_store_settings_are_503_then_created_then_replaced(
    owner_client: AsyncClient,
    admin_session: async_sessionmaker[AsyncSession],
) -> None:
    missing = await owner_client.get("/api/v1/admin/store-settings")
    assert missing.status_code == 503
    assert missing.json() == {"detail": "store_not_configured"}

    created = await owner_client.put(
        "/api/v1/admin/store-settings",
        json={
            "delivery_fee_minor": 150_000,
            "order_cutoff_time": "16:30",
            "max_advance_days": 7,
        },
    )
    assert created.status_code == 200
    assert created.json() == {
        "delivery_fee_minor": 150_000,
        "order_cutoff_time": "16:30",
        "max_advance_days": 7,
        "currency": "NGN",
        "timezone": "Africa/Lagos",
    }

    replaced = await owner_client.put(
        "/api/v1/admin/store-settings",
        json={
            "delivery_fee_minor": 200_000,
            "order_cutoff_time": "18:00",
            "max_advance_days": 3,
        },
    )
    assert replaced.status_code == 200
    assert replaced.json()["delivery_fee_minor"] == 200_000
    assert replaced.json()["order_cutoff_time"] == "18:00"
    assert replaced.json()["max_advance_days"] == 3

    fetched = await owner_client.get("/api/v1/admin/store-settings")
    assert fetched.json() == replaced.json()
    async with admin_session() as session:
        rows = list(await session.scalars(select(StoreSettings)))
    assert len(rows) == 1
    assert rows[0].id == 1
    assert rows[0].order_cutoff_time == time(18, 0)


@pytest.mark.parametrize(
    "body",
    [
        {
            "delivery_fee_minor": -1,
            "order_cutoff_time": "16:30",
            "max_advance_days": 7,
        },
        {
            "delivery_fee_minor": 1,
            "order_cutoff_time": "16:30",
            "max_advance_days": -1,
        },
        {
            "delivery_fee_minor": 1,
            "order_cutoff_time": "25:00",
            "max_advance_days": 1,
        },
        {
            "delivery_fee_minor": 1,
            "order_cutoff_time": "not-a-time",
            "max_advance_days": 1,
        },
        {"order_cutoff_time": "16:30", "max_advance_days": 1},
        {"delivery_fee_minor": 1, "max_advance_days": 1},
    ],
)
async def test_admin_rejects_invalid_store_settings(
    owner_client: AsyncClient,
    body: dict[str, object],
) -> None:
    response = await owner_client.put("/api/v1/admin/store-settings", json=body)
    assert response.status_code == 422


async def test_no_delete_endpoint_exists_for_the_catalog(
    owner_client: AsyncClient,
    admin_session: async_sessionmaker[AsyncSession],
) -> None:
    menu_item_id = await _add_menu_item(admin_session, name="Keep me")
    service_id = await _add_service(admin_session, name="Keep me")
    async with admin_session.begin() as session:
        session.add(
            StoreSettings(
                id=1,
                delivery_fee_minor=0,
                order_cutoff_time=time(16, 0),
                max_advance_days=1,
                updated_at=_now(),
            )
        )

    responses = [
        await owner_client.delete(f"/api/v1/admin/menu-items/{menu_item_id}"),
        await owner_client.delete(f"/api/v1/admin/services/{service_id}"),
        await owner_client.delete("/api/v1/admin/store-settings"),
    ]

    assert [response.status_code for response in responses] == [405, 405, 405]
    async with admin_session() as session:
        assert await session.get(MenuItem, menu_item_id) is not None
        assert await session.get(Service, service_id) is not None
        assert await session.get(StoreSettings, 1) is not None


async def test_store_settings_put_ignores_unknown_fields(
    owner_client: AsyncClient,
) -> None:
    response = await owner_client.put(
        "/api/v1/admin/store-settings",
        json={
            "delivery_fee_minor": 1_000,
            "order_cutoff_time": "16:30",
            "max_advance_days": 1,
            "currency": "USD",
            "id": 2,
        },
    )
    assert response.status_code == 200
    assert response.json()["currency"] == "NGN"


async def test_deactivating_hides_a_menu_item_from_the_public_menu(
    owner_client: AsyncClient,
    admin_session: async_sessionmaker[AsyncSession],
) -> None:
    menu_item_id = await _add_menu_item(admin_session, name="Doomed dish")

    before = await owner_client.get("/api/v1/menu")
    patched = await owner_client.patch(
        f"/api/v1/admin/menu-items/{menu_item_id}", json={"is_active": False}
    )
    after = await owner_client.get("/api/v1/menu")

    assert patched.status_code == 200
    assert [item["name"] for item in before.json()["items"]] == ["Doomed dish"]
    assert after.json()["items"] == []


async def test_deactivating_a_service_hides_it_from_the_public_services(
    owner_client: AsyncClient,
    admin_session: async_sessionmaker[AsyncSession],
) -> None:
    service_id = await _add_service(admin_session, name="Temporary")
    before = await owner_client.get("/api/v1/services")
    await owner_client.patch(
        f"/api/v1/admin/services/{service_id}", json={"is_active": False}
    )
    after = await owner_client.get("/api/v1/services")

    assert [item["name"] for item in before.json()["items"]] == ["Temporary"]
    assert after.json()["items"] == []


async def test_store_settings_put_is_visible_on_the_public_store(
    owner_client: AsyncClient,
) -> None:
    public_before = await owner_client.get("/api/v1/store")
    await owner_client.put(
        "/api/v1/admin/store-settings",
        json={
            "delivery_fee_minor": 75_000,
            "order_cutoff_time": "20:15",
            "max_advance_days": 2,
        },
    )
    public_after = await owner_client.get("/api/v1/store")

    assert public_before.status_code == 503
    assert public_after.json()["delivery_fee_minor"] == 75_000
    assert public_after.json()["order_cutoff_time"] == "20:15"
    assert public_after.json()["currency"] == settings.currency


async def test_concurrent_store_settings_writes_leave_a_single_row(
    admin_session: async_sessionmaker[AsyncSession],
) -> None:
    async def put(fee: int) -> None:
        async with admin_session() as session:
            await put_store_settings(
                session,
                delivery_fee_minor=fee,
                order_cutoff_time=time(16, 0),
                max_advance_days=7,
            )

    async with asyncio.TaskGroup() as task_group:
        task_group.create_task(put(100_000))
        task_group.create_task(put(200_000))

    async with admin_session() as session:
        rows = list(await session.scalars(select(StoreSettings)))
    assert len(rows) == 1
    assert rows[0].delivery_fee_minor in {100_000, 200_000}
