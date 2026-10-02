from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.cursors import InvalidCursor
from app.db.session import get_session
from app.models import User
from app.schemas.orders import (
    CursorPage,
    OrderCreate,
    OrderDetailResponse,
    OrderResponse,
)
from app.schemas.products import ProductResponse
from app.schemas.user import MeResponse
from app.services.orders import (
    IdempotencyKeyReused,
    OrderNotCancellable,
    OrderNotFound,
    UnavailableProducts,
    cancel_order,
    create_order,
    get_order_detail,
    get_product,
    list_orders,
    list_products,
)

router = APIRouter()


@router.get("/me", response_model=MeResponse)
async def get_me(
    user: Annotated[User, Depends(get_current_user)],
) -> MeResponse:
    return MeResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
    )


@router.get("/products", response_model=CursorPage[ProductResponse])
async def get_products(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> CursorPage[ProductResponse]:
    try:
        return await list_products(session, limit=limit, cursor=cursor)
    except InvalidCursor as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_cursor",
        ) from error


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product_by_id(
    product_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProductResponse:
    product = await get_product(session, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return product


@router.post("/orders", response_model=OrderResponse)
async def post_order(
    request: OrderCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", min_length=1, max_length=255),
    ] = None,
) -> OrderResponse:
    try:
        return await create_order(
            session,
            user=user,
            request=request,
            idempotency_key=idempotency_key,
        )
    except UnavailableProducts as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"unavailable_product_ids": error.product_ids},
        ) from error
    except IdempotencyKeyReused as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="idempotency_key_reused",
        ) from error


@router.get("/orders", response_model=CursorPage[OrderResponse])
async def get_orders(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> CursorPage[OrderResponse]:
    try:
        return await list_orders(
            session,
            user_id=user.id,
            limit=limit,
            cursor=cursor,
        )
    except InvalidCursor as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_cursor",
        ) from error


@router.get("/orders/{order_id}", response_model=OrderDetailResponse)
async def get_order_by_id(
    order_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrderDetailResponse:
    order = await get_order_detail(
        session,
        user_id=user.id,
        order_id=order_id,
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return order


@router.post("/orders/{order_id}/cancel", response_model=OrderResponse)
async def post_cancel_order(
    order_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrderResponse:
    try:
        return await cancel_order(session, user_id=user.id, order_id=order_id)
    except OrderNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    except OrderNotCancellable as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="order_not_pending",
        ) from error
