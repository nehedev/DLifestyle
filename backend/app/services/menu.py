from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.cursors import decode_created_cursor, encode_created_cursor
from app.models import MenuItem, MenuItemDay


class MenuItemNotFound(Exception):
    pass


async def list_menu_items(
    session: AsyncSession,
    *,
    limit: int,
    cursor: str | None,
) -> tuple[list[MenuItem], str | None]:
    statement = select(MenuItem).options(selectinload(MenuItem.days))
    if cursor is not None:
        created_at, menu_item_id = decode_created_cursor(cursor)
        statement = statement.where(
            or_(
                MenuItem.created_at < created_at,
                and_(MenuItem.created_at == created_at, MenuItem.id < menu_item_id),
            )
        )
    statement = statement.order_by(
        MenuItem.created_at.desc(), MenuItem.id.desc()
    ).limit(limit + 1)
    menu_items = list(await session.scalars(statement))
    has_next = len(menu_items) > limit
    page = menu_items[:limit]
    last_item = page[-1] if page else None
    next_cursor = (
        encode_created_cursor(last_item.created_at, last_item.id)
        if has_next and last_item is not None
        else None
    )
    return page, next_cursor


async def create_menu_item(
    session: AsyncSession,
    *,
    name: str,
    description: str | None,
    category: str,
    image_url: str | None,
    image_alt: str | None,
    price_minor: int,
    weekdays: list[int],
    is_active: bool,
    is_sold_out: bool,
) -> MenuItem:
    now = datetime.now(UTC)
    menu_item = MenuItem(
        name=name,
        description=description,
        category=category,
        image_url=image_url,
        image_alt=image_alt,
        price_minor=price_minor,
        is_active=is_active,
        is_sold_out=is_sold_out,
        created_at=now,
        updated_at=now,
    )
    menu_item.days = [MenuItemDay(weekday=weekday) for weekday in sorted(set(weekdays))]
    session.add(menu_item)
    await session.commit()
    return menu_item


async def patch_menu_item(
    session: AsyncSession,
    *,
    menu_item_id: int,
    changes: dict[str, object],
    weekdays: list[int] | None = None,
) -> MenuItem:
    menu_item = await session.get(MenuItem, menu_item_id)
    if menu_item is None:
        raise MenuItemNotFound
    for field, value in changes.items():
        if value is not None:
            setattr(menu_item, field, value)
    menu_item.updated_at = datetime.now(UTC)
    if weekdays is not None:
        menu_item.days = [
            MenuItemDay(weekday=weekday) for weekday in sorted(set(weekdays))
        ]
    await session.commit()
    return menu_item


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
