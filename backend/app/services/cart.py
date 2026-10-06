from datetime import UTC, date, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CartItem, MenuItem, Service
from app.schemas.cart import CartItemInput

FOOD = "food"
SERVICE = "service"


class UnknownCartTarget(Exception):
    pass


def _cart_key(item: CartItemInput) -> tuple[str, int, date | None]:
    target_id = item.menu_item_id if item.kind == FOOD else item.service_id
    assert target_id is not None
    return (item.kind, target_id, item.preferred_date)


async def list_cart(session: AsyncSession, *, user_id: int) -> list[CartItem]:
    statement = (
        select(CartItem).where(CartItem.user_id == user_id).order_by(CartItem.id)
    )
    return list(await session.scalars(statement))


async def replace_cart(
    session: AsyncSession,
    *,
    user_id: int,
    items: list[CartItemInput],
) -> list[CartItem]:
    """Replace the user's whole cart with ``items``.

    The request is treated as a full snapshot: the cart is deleted and rebuilt
    in one transaction. Cart lines reference catalog rows only; prices and
    availability are resolved again when an order is created.
    """
    unique_items: list[CartItemInput] = []
    seen: set[tuple[str, int, date | None]] = set()
    for item in items:
        key = _cart_key(item)
        if key in seen:
            continue
        seen.add(key)
        unique_items.append(item)

    food_ids = {
        item.menu_item_id
        for item in unique_items
        if item.kind == FOOD and item.menu_item_id is not None
    }
    service_ids = {
        item.service_id
        for item in unique_items
        if item.kind == SERVICE and item.service_id is not None
    }

    if food_ids:
        found_food = set(
            await session.scalars(select(MenuItem.id).where(MenuItem.id.in_(food_ids)))
        )
        if found_food != food_ids:
            raise UnknownCartTarget
    if service_ids:
        found_services = set(
            await session.scalars(select(Service.id).where(Service.id.in_(service_ids)))
        )
        if found_services != service_ids:
            raise UnknownCartTarget

    now = datetime.now(UTC)
    await session.execute(delete(CartItem).where(CartItem.user_id == user_id))
    for item in unique_items:
        session.add(
            CartItem(
                user_id=user_id,
                kind=item.kind,
                menu_item_id=item.menu_item_id,
                service_id=item.service_id,
                quantity=item.quantity,
                preferred_date=item.preferred_date,
                created_at=now,
                updated_at=now,
            )
        )
    await session.commit()
    return await list_cart(session, user_id=user_id)
