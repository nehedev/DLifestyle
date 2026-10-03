import logging
from datetime import UTC, date, datetime

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.cursors import decode_created_cursor, encode_created_cursor
from app.models import Order, OrderItem, Payment, User
from app.schemas.orders import (
    CursorPage,
    OrderCreate,
    OrderDetailResponse,
    OrderItemResponse,
    OrderResponse,
    PaymentSummary,
)
from app.services.menu import (
    find_unavailable_menu_item_ids,
    is_orderable,
    load_menu_items_with_days,
)
from app.services.store_settings import (
    has_cutoff_passed,
    is_ordering_open,
    require_store_settings,
)
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


class OrderingClosedForDate(Exception):
    pass


class OrderCanNoLongerBeFulfilled(Exception):
    pass


class UnavailableMenuItems(Exception):
    def __init__(self, menu_item_ids: list[int]) -> None:
        self.menu_item_ids = menu_item_ids


class IdempotencyKeyReused(Exception):
    pass


class OrderNotFound(Exception):
    pass


class OrderNotCancellable(Exception):
    pass


async def _get_idempotent_order(
    session: AsyncSession,
    *,
    user_id: int,
    idempotency_key: str,
) -> Order | None:
    return await session.scalar(
        select(Order).where(
            Order.user_id == user_id,
            Order.idempotency_key == idempotency_key,
        )
    )


def _stored_order_payload(order: Order, order_items: list[OrderItem]) -> tuple:
    return (
        sorted((item.menu_item_id, item.quantity) for item in order_items),
        order.fulfillment_type,
        order.fulfillment_date,
        order.contact,
        order.notes,
    )


def _requested_order_payload(request: OrderCreate) -> tuple:
    return (
        sorted((item.menu_item_id, item.quantity) for item in request.items),
        request.fulfillment_type,
        request.fulfillment_date,
        request.contact.model_dump(),
        request.notes,
    )


async def _load_order_items(
    session: AsyncSession,
    order_id: int,
) -> list[OrderItem]:
    return list(
        await session.scalars(
            select(OrderItem)
            .where(OrderItem.order_id == order_id)
            .order_by(OrderItem.menu_item_id)
        )
    )


async def _order_response(
    session: AsyncSession,
    order: Order,
    *,
    include_payments: bool = False,
) -> OrderResponse | OrderDetailResponse:
    order_items = await _load_order_items(session, order.id)
    response_values = {
        "id": order.id,
        "status": order.status,
        "fulfillment_type": order.fulfillment_type,
        "fulfillment_date": order.fulfillment_date,
        "contact": order.contact,
        "notes": order.notes,
        "items_total_minor": order.items_total_minor,
        "delivery_fee_minor": order.delivery_fee_minor,
        "total_minor": order.total_minor,
        "currency": order.currency,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "items": [
            OrderItemResponse(
                name=item.name,
                quantity=item.quantity,
                unit_price_minor=item.unit_price_minor,
            )
            for item in order_items
        ],
    }
    if not include_payments:
        return OrderResponse(**response_values)

    payments = list(
        await session.scalars(
            select(Payment).where(Payment.order_id == order.id).order_by(Payment.id)
        )
    )
    return OrderDetailResponse(
        **response_values,
        payments=[
            PaymentSummary(
                id=payment.id,
                status=payment.status,
                amount_minor=payment.amount_minor,
                currency=payment.currency,
            )
            for payment in payments
        ],
    )


async def _check_idempotent_payload(
    session: AsyncSession,
    order: Order,
    request: OrderCreate,
) -> OrderResponse:
    order_items = await _load_order_items(session, order.id)
    if _stored_order_payload(order, order_items) != _requested_order_payload(request):
        raise IdempotencyKeyReused
    response = await _order_response(session, order)
    assert isinstance(response, OrderResponse)
    return response


def _order_items_by_id(request: OrderCreate) -> dict[int, int]:
    return {item.menu_item_id: item.quantity for item in request.items}


async def create_order(
    session: AsyncSession,
    *,
    user: User,
    request: OrderCreate,
    idempotency_key: str | None,
) -> OrderResponse:
    store_settings = await require_store_settings(session)

    if idempotency_key is not None:
        existing_order = await _get_idempotent_order(
            session,
            user_id=user.id,
            idempotency_key=idempotency_key,
        )
        if existing_order is not None:
            return await _check_idempotent_payload(session, existing_order, request)

    now = datetime.now(UTC)
    if not is_ordering_open(
        store_settings,
        fulfillment_date=request.fulfillment_date,
        now=now,
    ):
        raise OrderingClosedForDate

    weekday = request.fulfillment_date.isoweekday()
    unavailable_menu_item_ids = await find_unavailable_menu_item_ids(
        session,
        _order_items_by_id(request),
        weekday=weekday,
    )
    if unavailable_menu_item_ids:
        raise UnavailableMenuItems(unavailable_menu_item_ids)

    menu_items = await load_menu_items_with_days(session, _order_items_by_id(request))
    menu_items_by_id = {menu_item.id: menu_item for menu_item in menu_items}
    quantities = _order_items_by_id(request)
    items_total_minor = sum(
        menu_items_by_id[menu_item_id].price_minor * quantity
        for menu_item_id, quantity in quantities.items()
    )
    delivery_fee_minor = (
        store_settings.delivery_fee_minor
        if request.fulfillment_type == "delivery"
        else 0
    )
    order = Order(
        user_id=user.id,
        status="pending",
        fulfillment_type=request.fulfillment_type,
        fulfillment_date=request.fulfillment_date,
        contact=request.contact.model_dump(),
        notes=request.notes,
        items_total_minor=items_total_minor,
        delivery_fee_minor=delivery_fee_minor,
        total_minor=items_total_minor + delivery_fee_minor,
        currency=settings.currency,
        idempotency_key=idempotency_key,
        created_at=now,
        updated_at=now,
    )
    session.add(order)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        if idempotency_key is None:
            raise
        existing_order = await _get_idempotent_order(
            session,
            user_id=user.id,
            idempotency_key=idempotency_key,
        )
        if existing_order is None:
            raise
        return await _check_idempotent_payload(session, existing_order, request)

    session.add_all(
        OrderItem(
            order_id=order.id,
            menu_item_id=menu_item_id,
            name=menu_items_by_id[menu_item_id].name,
            quantity=quantity,
            unit_price_minor=menu_items_by_id[menu_item_id].price_minor,
        )
        for menu_item_id, quantity in sorted(quantities.items())
    )
    await session.commit()
    response = await _order_response(session, order)
    assert isinstance(response, OrderResponse)
    return response


async def list_orders(
    session: AsyncSession,
    *,
    user_id: int,
    limit: int,
    cursor: str | None,
) -> CursorPage[OrderResponse]:
    statement = select(Order).where(Order.user_id == user_id)
    if cursor is not None:
        created_at, order_id = decode_created_cursor(cursor)
        statement = statement.where(
            or_(
                Order.created_at < created_at,
                and_(Order.created_at == created_at, Order.id < order_id),
            )
        )
    orders = list(
        await session.scalars(
            statement.order_by(Order.created_at.desc(), Order.id.desc()).limit(
                limit + 1
            )
        )
    )
    has_next = len(orders) > limit
    page = orders[:limit]
    response_items = []
    for order in page:
        response = await _order_response(session, order)
        assert isinstance(response, OrderResponse)
        response_items.append(response)
    last_order = page[-1] if page else None
    return CursorPage(
        items=response_items,
        next_cursor=encode_created_cursor(last_order.created_at, last_order.id)
        if has_next and last_order is not None
        else None,
    )


async def get_order_detail(
    session: AsyncSession,
    *,
    user_id: int,
    order_id: int,
) -> OrderDetailResponse | None:
    order = await session.scalar(
        select(Order).where(Order.id == order_id, Order.user_id == user_id)
    )
    if order is None:
        return None
    response = await _order_response(session, order, include_payments=True)
    assert isinstance(response, OrderDetailResponse)
    return response


async def find_unfulfillable_menu_item_ids(
    session: AsyncSession,
    *,
    order_id: int,
    fulfillment_date: date,
) -> list[int]:
    """Menu items on the order that can no longer be served on that date."""
    order_items = await _load_order_items(session, order_id)
    menu_items = await load_menu_items_with_days(
        session, [item.menu_item_id for item in order_items]
    )
    menu_items_by_id = {menu_item.id: menu_item for menu_item in menu_items}
    weekday = fulfillment_date.isoweekday()
    return sorted(
        item.menu_item_id
        for item in order_items
        if item.menu_item_id not in menu_items_by_id
        or not is_orderable(menu_items_by_id[item.menu_item_id], weekday=weekday)
    )


async def cancel_order(
    session: AsyncSession,
    *,
    user_id: int,
    order_id: int,
) -> OrderResponse:
    transition = await session.execute(
        update(Order)
        .where(
            Order.id == order_id,
            Order.user_id == user_id,
            Order.status == "pending",
        )
        .values(status="cancelled", updated_at=datetime.now(UTC))
        .returning(Order.id)
    )
    if transition.scalar_one_or_none() != order_id:
        await session.rollback()
        order = await session.scalar(
            select(Order).where(Order.id == order_id, Order.user_id == user_id)
        )
        if order is None:
            raise OrderNotFound
        raise OrderNotCancellable

    await session.commit()
    logger.info("order.user_cancelled")
    celery_app.send_task("send_order_cancelled_email", args=[order_id])
    order = await session.scalar(
        select(Order).where(Order.id == order_id, Order.user_id == user_id)
    )
    if order is None:
        raise RuntimeError("Cancelled order could not be reloaded")
    response = await _order_response(session, order)
    assert isinstance(response, OrderResponse)
    return response


async def can_still_be_fulfilled(session: AsyncSession, *, order: Order) -> None:
    """Raise when the order can no longer be fulfilled, per spec section 4.

    Returns nothing when the order is still fulfillable. The caller
    decides which failure to report; this only classifies it.
    """
    store_settings = await require_store_settings(session)
    if has_cutoff_passed(
        store_settings,
        fulfillment_date=order.fulfillment_date,
        now=datetime.now(UTC),
    ):
        raise OrderCanNoLongerBeFulfilled
    unavailable = await find_unfulfillable_menu_item_ids(
        session,
        order_id=order.id,
        fulfillment_date=order.fulfillment_date,
    )
    if unavailable:
        raise UnavailableMenuItems(unavailable)
