import logging
from datetime import UTC, datetime

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.cursors import (
    decode_order_cursor,
    decode_product_cursor,
    encode_order_cursor,
    encode_product_cursor,
)
from app.models import Order, OrderItem, Payment, Product, User
from app.schemas.orders import (
    CursorPage,
    OrderCreate,
    OrderDetailResponse,
    OrderItemResponse,
    OrderResponse,
    PaymentSummary,
)
from app.schemas.products import ProductResponse

logger = logging.getLogger(__name__)


class UnavailableProducts(Exception):
    def __init__(self, product_ids: list[int]) -> None:
        self.product_ids = product_ids


class IdempotencyKeyReused(Exception):
    pass


class OrderNotFound(Exception):
    pass


class OrderNotCancellable(Exception):
    pass


def _product_response(product: Product) -> ProductResponse:
    return ProductResponse(
        id=product.id,
        name=product.name,
        price_minor=product.price_minor,
        stock_quantity=product.stock_quantity,
        is_active=product.is_active,
    )


async def list_products(
    session: AsyncSession,
    *,
    limit: int,
    cursor: str | None,
) -> CursorPage[ProductResponse]:
    statement = select(Product).where(Product.is_active.is_(True))
    if cursor is not None:
        statement = statement.where(Product.id > decode_product_cursor(cursor))
    products = list(
        await session.scalars(statement.order_by(Product.id).limit(limit + 1))
    )
    has_next = len(products) > limit
    page = products[:limit]
    return CursorPage(
        items=[_product_response(product) for product in page],
        next_cursor=encode_product_cursor(page[-1].id) if has_next and page else None,
    )


async def get_product(
    session: AsyncSession,
    product_id: int,
) -> ProductResponse | None:
    product = await session.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.is_active.is_(True),
        )
    )
    return _product_response(product) if product is not None else None


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


async def _order_response(
    session: AsyncSession,
    order: Order,
    *,
    include_payments: bool = False,
) -> OrderResponse | OrderDetailResponse:
    order_items = list(
        await session.scalars(
            select(OrderItem)
            .where(OrderItem.order_id == order.id)
            .order_by(OrderItem.product_id)
        )
    )
    response_values = {
        "id": order.id,
        "status": order.status,
        "total_minor": order.total_minor,
        "currency": order.currency,
        "shipping_address": order.shipping_address,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "items": [
            OrderItemResponse(
                product_id=item.product_id,
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
    existing_items = list(
        await session.execute(
            select(OrderItem.product_id, OrderItem.quantity).where(
                OrderItem.order_id == order.id
            )
        )
    )
    existing_payload = sorted((row.product_id, row.quantity) for row in existing_items)
    requested_payload = sorted(
        (item.product_id, item.quantity) for item in request.items
    )
    requested_address = request.shipping_address.model_dump()
    if (
        existing_payload != requested_payload
        or order.shipping_address != requested_address
    ):
        raise IdempotencyKeyReused
    response = await _order_response(session, order)
    assert isinstance(response, OrderResponse)
    return response


async def create_order(
    session: AsyncSession,
    *,
    user: User,
    request: OrderCreate,
    idempotency_key: str | None,
) -> OrderResponse:
    if idempotency_key is not None:
        existing_order = await _get_idempotent_order(
            session,
            user_id=user.id,
            idempotency_key=idempotency_key,
        )
        if existing_order is not None:
            return await _check_idempotent_payload(session, existing_order, request)

    requested_ids = [item.product_id for item in request.items]
    products = list(
        await session.scalars(
            select(Product).where(
                Product.id.in_(requested_ids),
                Product.is_active.is_(True),
            )
        )
    )
    products_by_id = {product.id: product for product in products}
    unavailable_ids = sorted(set(requested_ids) - products_by_id.keys())
    if unavailable_ids:
        await session.rollback()
        raise UnavailableProducts(unavailable_ids)

    total_minor = sum(
        products_by_id[item.product_id].price_minor * item.quantity
        for item in request.items
    )
    now = datetime.now(UTC)
    order = Order(
        user_id=user.id,
        status="pending",
        total_minor=total_minor,
        currency=settings.currency,
        shipping_address=request.shipping_address.model_dump(),
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

    unavailable_ids = []
    for item in sorted(request.items, key=lambda requested: requested.product_id):
        result = await session.execute(
            update(Product)
            .where(
                Product.id == item.product_id,
                Product.is_active.is_(True),
                Product.stock_quantity >= item.quantity,
            )
            .values(stock_quantity=Product.stock_quantity - item.quantity)
            .returning(Product.id)
        )
        if result.scalar_one_or_none() != item.product_id:
            unavailable_ids.append(item.product_id)

    if unavailable_ids:
        await session.rollback()
        raise UnavailableProducts(unavailable_ids)

    session.add_all(
        OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            quantity=item.quantity,
            unit_price_minor=products_by_id[item.product_id].price_minor,
        )
        for item in request.items
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
        created_at, order_id = decode_order_cursor(cursor)
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
        next_cursor=encode_order_cursor(last_order.created_at, last_order.id)
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


async def cancel_order(
    session: AsyncSession,
    *,
    user_id: int,
    order_id: int,
) -> OrderResponse:
    order_items = list(
        await session.scalars(
            select(OrderItem)
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.id == order_id, Order.user_id == user_id)
            .order_by(OrderItem.product_id)
        )
    )
    now = datetime.now(UTC)
    transition = await session.execute(
        update(Order)
        .where(
            Order.id == order_id,
            Order.user_id == user_id,
            Order.status == "pending",
        )
        .values(status="cancelled", updated_at=now)
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

    for item in order_items:
        result = await session.execute(
            update(Product)
            .where(Product.id == item.product_id)
            .values(stock_quantity=Product.stock_quantity + item.quantity)
            .returning(Product.id)
        )
        if result.scalar_one_or_none() != item.product_id:
            await session.rollback()
            raise RuntimeError("Order item references a missing product")

    await session.commit()
    logger.info("order.user_cancelled")
    order = await session.scalar(
        select(Order).where(Order.id == order_id, Order.user_id == user_id)
    )
    if order is None:
        raise RuntimeError("Cancelled order could not be reloaded")
    response = await _order_response(session, order)
    assert isinstance(response, OrderResponse)
    return response
