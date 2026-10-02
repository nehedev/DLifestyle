"""Create the starting services and menu from docs/spec.md section 15.

Safe to run repeatedly: existing rows are left exactly as they are, so an
owner's price, activation, or sold-out edit is never overwritten.
"""

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

SERVICES: tuple[str, ...] = (
    "Personal chef and catering",
    "Home cleaning",
    "Errand running",
    "Home organization",
)

MENU: tuple[tuple[str, int, tuple[int, ...]], ...] = (
    ("Jollof rice + chicken", 350_000, (1,)),
    ("Jollof rice + fried plantain", 250_000, (1,)),
    ("Assorted moi moi", 150_000, (1,)),
    ("Beans + fried plantain", 250_000, (2,)),
    ("Beans + plantain + egg", 300_000, (2,)),
    ("Jollof spaghetti + chicken", 300_000, (3,)),
    ("Spaghetti + egg", 200_000, (3,)),
    ("Noodles + egg", 200_000, (3,)),
    ("Fried rice + chicken", 350_000, (4,)),
    ("Semo + egusi soup + protein", 350_000, (4, 5)),
    ("Semo + vegetable soup + protein", 350_000, (4,)),
    ("Amala + ewedu + protein", 300_000, (5,)),
    ("White rice + stew + chicken", 300_000, (6,)),
)


async def seed_catalog(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> list[str]:
    from app.db.session import SessionFactory
    from app.models import MenuItem, MenuItemDay, Service

    if session_factory is None:
        session_factory = SessionFactory

    now = datetime.now(UTC)
    menu_names = [name for name, _, _ in MENU]
    created: list[str] = []

    async with session_factory.begin() as session:
        existing_service_names = set(await session.scalars(select(Service.name)))
        for sort_order, name in enumerate(SERVICES, start=1):
            if name in existing_service_names:
                continue
            session.add(
                Service(
                    name=name,
                    description="",
                    is_active=True,
                    sort_order=sort_order,
                    created_at=now,
                    updated_at=now,
                )
            )
            created.append(f"service {name}")

        menu_items = {
            menu_item.name: menu_item
            for menu_item in await session.scalars(
                select(MenuItem).where(MenuItem.name.in_(menu_names))
            )
        }
        for name, price_minor, _ in MENU:
            if name in menu_items:
                continue
            menu_item = MenuItem(
                name=name,
                price_minor=price_minor,
                is_active=True,
                is_sold_out=False,
                created_at=now,
                updated_at=now,
            )
            session.add(menu_item)
            menu_items[name] = menu_item
            created.append(f"menu item {name}")
        await session.flush()

        existing_days = {
            (row.menu_item_id, row.weekday)
            for row in await session.execute(
                select(MenuItemDay.menu_item_id, MenuItemDay.weekday).where(
                    MenuItemDay.menu_item_id.in_(
                        [menu_item.id for menu_item in menu_items.values()]
                    )
                )
            )
        }
        for name, _, weekdays in MENU:
            menu_item = menu_items[name]
            for weekday in weekdays:
                if (menu_item.id, weekday) in existing_days:
                    continue
                session.add(MenuItemDay(menu_item_id=menu_item.id, weekday=weekday))
                existing_days.add((menu_item.id, weekday))
                created.append(f"menu day {name} weekday {weekday}")

    return created


def main() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    created = asyncio.run(seed_catalog())
    for label in created:
        print(f"created {label}")
    if not created:
        print("catalog already complete, nothing to do")


if __name__ == "__main__":
    main()
