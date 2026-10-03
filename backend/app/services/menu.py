from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import MenuItem


async def list_active_menu_items(session: AsyncSession) -> list[MenuItem]:
    statement = (
        select(MenuItem)
        .where(MenuItem.is_active.is_(True))
        .options(selectinload(MenuItem.days))
        .order_by(MenuItem.name)
    )
    return list(await session.scalars(statement))


async def load_menu_items_with_days(
    session: AsyncSession,
    menu_item_ids: Iterable[int],
) -> list[MenuItem]:
    statement = (
        select(MenuItem)
        .where(MenuItem.id.in_(set(menu_item_ids)))
        .options(selectinload(MenuItem.days))
    )
    return list(await session.scalars(statement))


def is_orderable(menu_item: MenuItem, *, weekday: int) -> bool:
    return (
        menu_item.is_active
        and not menu_item.is_sold_out
        and weekday in {day.weekday for day in menu_item.days}
    )


async def find_unavailable_menu_item_ids(
    session: AsyncSession,
    menu_item_ids: Iterable[int],
    *,
    weekday: int,
) -> list[int]:
    requested_ids = set(menu_item_ids)
    menu_items = await load_menu_items_with_days(session, requested_ids)
    menu_items_by_id = {menu_item.id: menu_item for menu_item in menu_items}
    return sorted(
        menu_item_id
        for menu_item_id in requested_ids
        if menu_item_id not in menu_items_by_id
        or not is_orderable(menu_items_by_id[menu_item_id], weekday=weekday)
    )
