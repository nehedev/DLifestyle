from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.models import MenuItem, MenuItemDay, Service
from scripts.seed_catalog import MENU, SERVICES, seed_catalog

SPEC_MENU: dict[str, tuple[int, set[int], str]] = {
    "Jollof rice + chicken": (350_000, {1}, "Rice"),
    "Jollof rice + fried plantain": (250_000, {1}, "Rice"),
    "Assorted moi moi": (150_000, {1}, "Beans"),
    "Beans + fried plantain": (250_000, {2}, "Beans"),
    "Beans + plantain + egg": (300_000, {2}, "Beans"),
    "Jollof spaghetti + chicken": (300_000, {3}, "Pasta"),
    "Spaghetti + egg": (200_000, {3}, "Pasta"),
    "Noodles + egg": (200_000, {3}, "Pasta"),
    "Fried rice + chicken": (350_000, {4}, "Rice"),
    "Semo + egusi soup + protein": (350_000, {4, 5}, "Soups"),
    "Semo + vegetable soup + protein": (350_000, {4}, "Soups"),
    "Amala + ewedu + protein": (300_000, {5}, "Soups"),
    "White rice + stew + chicken": (300_000, {6}, "Rice"),
}


def test_seed_data_matches_the_spec() -> None:
    assert SERVICES == (
        "Personal chef and catering",
        "Home cleaning",
        "Errand running",
        "Home organization",
    )
    assert {
        name: (price, set(days), category) for name, price, days, category in MENU
    } == SPEC_MENU


async def test_seed_catalog_creates_the_services_and_menu(
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    created = await seed_catalog(session_factory)

    assert len(created) == len(SERVICES) + len(MENU) + sum(
        len(days) for _, _, days, _ in MENU
    )

    async with session_factory() as session:
        services = list(
            await session.scalars(select(Service).order_by(Service.sort_order))
        )
        menu_items = {
            menu_item.name: menu_item
            for menu_item in await session.scalars(select(MenuItem))
        }
        days_by_item: dict[int, set[int]] = {}
        for menu_item_id, weekday in await session.execute(
            select(MenuItemDay.menu_item_id, MenuItemDay.weekday)
        ):
            days_by_item.setdefault(menu_item_id, set()).add(weekday)

    assert [service.name for service in services] == list(SERVICES)
    assert [service.sort_order for service in services] == [1, 2, 3, 4]
    assert all(service.is_active for service in services)

    assert set(menu_items) == set(SPEC_MENU)
    for name, (price_minor, weekdays, category) in SPEC_MENU.items():
        menu_item = menu_items[name]
        assert menu_item.price_minor == price_minor
        assert menu_item.category == category
        assert menu_item.is_active is True
        assert menu_item.is_sold_out is False
        assert days_by_item[menu_item.id] == weekdays


async def test_seed_catalog_is_safe_to_run_again_and_keeps_owner_edits(
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    await seed_catalog(session_factory)

    async with session_factory.begin() as session:
        dish = await session.scalar(
            select(MenuItem).where(MenuItem.name == "Jollof rice + chicken")
        )
        assert dish is not None
        await session.execute(
            update(MenuItem).where(MenuItem.id == dish.id).values(price_minor=999_000)
        )
        session.add(
            MenuItemDay(menu_item_id=dish.id, weekday=7),
        )

    assert await seed_catalog(session_factory) == []

    async with session_factory() as session:
        dish = await session.scalar(
            select(MenuItem).where(MenuItem.name == "Jollof rice + chicken")
        )
        service_count = await session.scalar(select(func.count()).select_from(Service))
        menu_count = await session.scalar(select(func.count()).select_from(MenuItem))
        assert dish is not None
        assert dish.price_minor == 999_000
        weekdays = set(
            await session.scalars(
                select(MenuItemDay.weekday).where(MenuItemDay.menu_item_id == dish.id)
            )
        )
    assert service_count == len(SERVICES)
    assert menu_count == len(SPEC_MENU)
    assert weekdays == {1, 7}


async def test_seed_catalog_fills_missing_weekdays_only(
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(UTC)
    async with session_factory.begin() as session:
        session.add(
            MenuItem(
                name="Semo + egusi soup + protein",
                category="Soups",
                price_minor=350_000,
                is_active=True,
                is_sold_out=False,
                created_at=now,
                updated_at=now,
            )
        )
        await session.flush()

    created = await seed_catalog(session_factory)

    assert "menu day Semo + egusi soup + protein weekday 5" in created
    async with session_factory() as session:
        dish = await session.scalar(
            select(MenuItem).where(MenuItem.name == "Semo + egusi soup + protein")
        )
        assert dish is not None
        weekdays = set(
            await session.scalars(
                select(MenuItemDay.weekday).where(MenuItemDay.menu_item_id == dish.id)
            )
        )
    assert weekdays == {4, 5}
