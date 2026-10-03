from collections.abc import AsyncIterator
from datetime import UTC, datetime, time

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.session import get_session
from app.main import app
from app.models import MenuItem, MenuItemDay, Service, StoreSettings


def _now() -> datetime:
    return datetime.now(UTC)


async def _add_menu_item(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    name: str,
    weekdays: tuple[int, ...] = (1, 2, 3, 4, 5),
    is_active: bool = True,
    is_sold_out: bool = False,
    description: str | None = None,
    price_minor: int = 350_000,
    category: str = "Rice",
    image_url: str | None = None,
    image_alt: str | None = None,
) -> int:
    async with session_factory.begin() as session:
        menu_item = MenuItem(
            name=name,
            description=description,
            category=category,
            image_url=image_url,
            image_alt=image_alt,
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
    sort_order: int,
    is_active: bool = True,
    description: str = "A service",
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


@pytest_asyncio.fixture
async def catalog(
    test_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def public_client(
    catalog: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with catalog() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)


async def test_menu_is_public_hides_inactive_and_flags_sold_out(
    public_client: AsyncClient,
    catalog: async_sessionmaker[AsyncSession],
) -> None:
    jollof_id = await _add_menu_item(
        catalog,
        name="Jollof rice + chicken",
        weekdays=(1, 4),
        description="One plate",
        price_minor=350_000,
        category="Rice",
        image_url="https://cdn.example/jollof.jpg",
        image_alt="A plate of jollof rice",
    )
    amala_id = await _add_menu_item(
        catalog, name="Amala + ewedu + protein", weekdays=(5,), price_minor=300_000
    )
    sold_out_id = await _add_menu_item(
        catalog, name="Sold out dish", weekdays=(2,), is_sold_out=True
    )
    await _add_menu_item(catalog, name="Hidden dish", is_active=False)

    response = await public_client.get("/api/v1/menu")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": amala_id,
                "name": "Amala + ewedu + protein",
                "description": None,
                "category": "Rice",
                "image_url": None,
                "image_alt": None,
                "price_minor": 300_000,
                "is_sold_out": False,
                "weekdays": [5],
            },
            {
                "id": jollof_id,
                "name": "Jollof rice + chicken",
                "description": "One plate",
                "category": "Rice",
                "image_url": "https://cdn.example/jollof.jpg",
                "image_alt": "A plate of jollof rice",
                "price_minor": 350_000,
                "is_sold_out": False,
                "weekdays": [1, 4],
            },
            {
                "id": sold_out_id,
                "name": "Sold out dish",
                "description": None,
                "category": "Rice",
                "image_url": None,
                "image_alt": None,
                "price_minor": 350_000,
                "is_sold_out": True,
                "weekdays": [2],
            },
        ]
    }


async def test_services_are_public_ordered_by_sort_order_and_filtered_by_active(
    public_client: AsyncClient,
    catalog: async_sessionmaker[AsyncSession],
) -> None:
    chef_id = await _add_service(catalog, name="Personal chef", sort_order=1)
    cleaning_id = await _add_service(
        catalog, name="Home cleaning", sort_order=2, description="Deep clean"
    )
    errands_id = await _add_service(
        catalog, name="Errand running", sort_order=3, description="Anything"
    )
    await _add_service(catalog, name="Retired service", sort_order=1, is_active=False)

    response = await public_client.get("/api/v1/services")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {"id": chef_id, "name": "Personal chef", "description": "A service"},
            {"id": cleaning_id, "name": "Home cleaning", "description": "Deep clean"},
            {"id": errands_id, "name": "Errand running", "description": "Anything"},
        ]
    }


async def test_store_is_503_until_configured(
    public_client: AsyncClient,
) -> None:
    response = await public_client.get("/api/v1/store")
    assert response.status_code == 503
    assert response.json() == {"detail": "store_not_configured"}


@pytest.mark.parametrize(
    ("cutoff", "expected"),
    [(time(16, 30), "16:30"), (time(9, 5), "09:05"), (time(0, 0), "00:00")],
)
async def test_store_reports_the_configured_settings(
    public_client: AsyncClient,
    catalog: async_sessionmaker[AsyncSession],
    cutoff: time,
    expected: str,
) -> None:
    async with catalog.begin() as session:
        session.add(
            StoreSettings(
                id=1,
                delivery_fee_minor=150_000,
                order_cutoff_time=cutoff,
                max_advance_days=7,
                updated_at=_now(),
            )
        )

    response = await public_client.get("/api/v1/store")

    assert response.status_code == 200
    assert response.json() == {
        "delivery_fee_minor": 150_000,
        "order_cutoff_time": expected,
        "max_advance_days": 7,
        "currency": "NGN",
        "timezone": "Africa/Lagos",
    }
    assert response.json()["timezone"] == settings.business_timezone


async def test_menu_and_services_are_readable_with_the_store_closed(
    public_client: AsyncClient,
    catalog: async_sessionmaker[AsyncSession],
) -> None:
    await _add_menu_item(catalog, name="Jollof rice + chicken")
    await _add_service(catalog, name="Home cleaning", sort_order=1)
    menu = await public_client.get("/api/v1/menu")
    services = await public_client.get("/api/v1/services")
    assert menu.status_code == 200
    assert services.status_code == 200
    assert len(menu.json()["items"]) == 1
    assert len(services.json()["items"]) == 1
