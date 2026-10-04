from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_admin_user
from app.core.config import settings
from app.core.cursors import InvalidCursor
from app.db.session import get_session
from app.models import MenuItem, Service, ServiceRequest, StoreSettings, User
from app.schemas.admin_orders import (
    AdminOrderListResponse,
    AdminOrderResponse,
    AdminOrderStatusBody,
    AdminPaymentListResponse,
    admin_order_list_response,
    admin_order_response,
    admin_payment_list_response,
)
from app.schemas.base import CursorPage
from app.schemas.menu import MenuItemAdmin, MenuItemCreate, MenuItemPatch
from app.schemas.service_requests import (
    ServiceRequestAdminResponse,
    ServiceRequestPatch,
)
from app.schemas.services import ServiceAdmin, ServiceCreate, ServicePatch
from app.schemas.store import StorePublic, StoreSettingsPut
from app.schemas.user import UserAdminResponse, UserRolePatch
from app.services import admin_orders, admin_users
from app.services import menu as menu_service
from app.services import service_requests as service_request_service
from app.services import services as services_service
from app.services.service_requests import (
    IllegalServiceRequestTransition,
    ServiceRequestNotFound,
)
from app.services.store_settings import get_store_settings, put_store_settings

router = APIRouter(prefix="/sudo", dependencies=[Depends(get_admin_user)])


def _admin_request_response(request: ServiceRequest) -> ServiceRequestAdminResponse:
    return ServiceRequestAdminResponse(
        id=request.id,
        user_id=request.user_id,
        service_id=request.service_id,
        preferred_date=request.preferred_date,
        location=request.location,
        details=request.details,
        contact_phone=request.contact_phone,
        status=request.status,
        quoted_amount_minor=request.quoted_amount_minor,
        owner_note=request.owner_note,
        created_at=request.created_at,
        updated_at=request.updated_at,
    )


def _menu_item_response(menu_item: MenuItem) -> MenuItemAdmin:
    return MenuItemAdmin(
        id=menu_item.id,
        name=menu_item.name,
        description=menu_item.description,
        category=menu_item.category,
        image_url=menu_item.image_url,
        image_alt=menu_item.image_alt,
        price_minor=menu_item.price_minor,
        is_active=menu_item.is_active,
        is_sold_out=menu_item.is_sold_out,
        weekdays=[day.weekday for day in menu_item.days],
        created_at=menu_item.created_at,
        updated_at=menu_item.updated_at,
    )


def _service_response(service: Service) -> ServiceAdmin:
    return ServiceAdmin(
        id=service.id,
        name=service.name,
        description=service.description,
        is_active=service.is_active,
        sort_order=service.sort_order,
        created_at=service.created_at,
        updated_at=service.updated_at,
    )


def _store_response(store_settings: StoreSettings) -> StorePublic:
    return StorePublic(
        delivery_fee_minor=store_settings.delivery_fee_minor,
        order_cutoff_time=store_settings.order_cutoff_time.strftime("%H:%M"),
        max_advance_days=store_settings.max_advance_days,
        currency=settings.currency,
        timezone=settings.business_timezone,
    )


@router.get("/menu-items", response_model=CursorPage[MenuItemAdmin])
async def get_admin_menu_items(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> CursorPage[MenuItemAdmin]:
    try:
        menu_items, next_cursor = await menu_service.list_menu_items(
            session, limit=limit, cursor=cursor
        )
    except InvalidCursor as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_cursor"
        ) from error
    return CursorPage(
        items=[_menu_item_response(menu_item) for menu_item in menu_items],
        next_cursor=next_cursor,
    )


@router.post("/menu-items", response_model=MenuItemAdmin)
async def post_admin_menu_item(
    body: MenuItemCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MenuItemAdmin:
    menu_item = await menu_service.create_menu_item(
        session,
        name=body.name,
        description=body.description,
        category=body.category,
        image_url=body.image_url,
        image_alt=body.image_alt,
        price_minor=body.price_minor,
        weekdays=body.weekdays,
        is_active=body.is_active,
        is_sold_out=body.is_sold_out,
    )
    return _menu_item_response(menu_item)


@router.patch("/menu-items/{menu_item_id}", response_model=MenuItemAdmin)
async def patch_admin_menu_item(
    menu_item_id: int,
    body: MenuItemPatch,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MenuItemAdmin:
    try:
        menu_item = await menu_service.patch_menu_item(
            session,
            menu_item_id=menu_item_id,
            changes={
                "name": body.name,
                "description": body.description,
                "category": body.category,
                "image_url": body.image_url,
                "image_alt": body.image_alt,
                "price_minor": body.price_minor,
                "is_active": body.is_active,
                "is_sold_out": body.is_sold_out,
            },
            weekdays=body.weekdays,
        )
    except menu_service.MenuItemNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    return _menu_item_response(menu_item)


@router.get("/services", response_model=CursorPage[ServiceAdmin])
async def get_admin_services(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> CursorPage[ServiceAdmin]:
    try:
        services, next_cursor = await services_service.list_services(
            session, limit=limit, cursor=cursor
        )
    except InvalidCursor as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_cursor"
        ) from error
    return CursorPage(
        items=[_service_response(service) for service in services],
        next_cursor=next_cursor,
    )


@router.post("/services", response_model=ServiceAdmin)
async def post_admin_service(
    body: ServiceCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ServiceAdmin:
    service = await services_service.create_service(
        session,
        name=body.name,
        description=body.description,
        is_active=body.is_active,
        sort_order=body.sort_order,
    )
    return _service_response(service)


@router.patch("/services/{service_id}", response_model=ServiceAdmin)
async def patch_admin_service(
    service_id: int,
    body: ServicePatch,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ServiceAdmin:
    try:
        service = await services_service.patch_service(
            session,
            service_id=service_id,
            changes={
                "name": body.name,
                "description": body.description,
                "is_active": body.is_active,
                "sort_order": body.sort_order,
            },
        )
    except services_service.ServiceNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    return _service_response(service)


@router.get("/store-settings", response_model=StorePublic)
async def get_admin_store_settings(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StorePublic:
    store_settings = await get_store_settings(session)
    if store_settings is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="store_not_configured",
        )
    return _store_response(store_settings)


@router.put("/store-settings", response_model=StorePublic)
async def put_admin_store_settings(
    body: StoreSettingsPut,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StorePublic:
    store_settings = await put_store_settings(
        session,
        delivery_fee_minor=body.delivery_fee_minor,
        order_cutoff_time=body.order_cutoff_time,
        max_advance_days=body.max_advance_days,
    )
    return _store_response(store_settings)


@router.get("/orders", response_model=CursorPage[AdminOrderListResponse])
async def get_admin_orders(
    session: Annotated[AsyncSession, Depends(get_session)],
    order_status: Annotated[
        str | None,
        Query(
            alias="status",
            pattern=r"^(pending|paid|preparing|ready|completed|cancelled)$",
        ),
    ] = None,
    fulfillment_date: date | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> CursorPage[AdminOrderListResponse]:
    try:
        orders, next_cursor = await admin_orders.list_admin_orders(
            session,
            status=order_status,
            fulfillment_date=fulfillment_date,
            limit=limit,
            cursor=cursor,
        )
    except InvalidCursor as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_cursor"
        ) from error
    return CursorPage(
        items=[admin_order_list_response(order) for order in orders],
        next_cursor=next_cursor,
    )


@router.get("/orders/{order_id}", response_model=AdminOrderResponse)
async def get_admin_order_by_id(
    order_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AdminOrderResponse:
    try:
        detail = await admin_orders.get_admin_order(session, order_id=order_id)
    except admin_orders.OrderNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    return admin_order_response(detail)


@router.post("/orders/{order_id}/status", response_model=AdminOrderResponse)
async def post_admin_order_status(
    order_id: int,
    body: AdminOrderStatusBody,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AdminOrderResponse:
    try:
        detail = await admin_orders.set_owner_order_status(
            session, order_id=order_id, new_status=body.status
        )
    except admin_orders.OrderNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    except (
        admin_orders.IllegalOrderTransition,
        admin_orders.OwnerCancelConflict,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="order_transition_not_allowed",
        ) from error
    return admin_order_response(detail)


@router.get("/payments", response_model=CursorPage[AdminPaymentListResponse])
async def get_admin_payments(
    session: Annotated[AsyncSession, Depends(get_session)],
    payment_status: Annotated[
        str | None,
        Query(
            alias="status",
            pattern=(
                r"^(initiated|succeeded|failed|needs_review|refund_pending"
                r"|refunded)$"
            ),
        ),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> CursorPage[AdminPaymentListResponse]:
    try:
        payments, next_cursor = await admin_orders.list_admin_payments(
            session,
            status=payment_status,
            limit=limit,
            cursor=cursor,
        )
    except InvalidCursor as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_cursor"
        ) from error
    return CursorPage(
        items=[admin_payment_list_response(payment) for payment in payments],
        next_cursor=next_cursor,
    )


@router.get("/service-requests", response_model=CursorPage[ServiceRequestAdminResponse])
async def get_admin_service_requests(
    session: Annotated[AsyncSession, Depends(get_session)],
    request_status: Annotated[
        str | None,
        Query(
            alias="status",
            pattern=r"^(requested|contacted|confirmed|completed|cancelled)$",
        ),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> CursorPage[ServiceRequestAdminResponse]:
    try:
        requests, next_cursor = await service_request_service.list_service_requests(
            session,
            user_id=None,
            status=request_status,
            limit=limit,
            cursor=cursor,
        )
    except InvalidCursor as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_cursor"
        ) from error
    return CursorPage(
        items=[_admin_request_response(request) for request in requests],
        next_cursor=next_cursor,
    )


@router.get(
    "/service-requests/{request_id}",
    response_model=ServiceRequestAdminResponse,
)
async def get_admin_service_request_by_id(
    request_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ServiceRequestAdminResponse:
    request = await service_request_service.get_service_request(
        session, request_id=request_id, user_id=None
    )
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _admin_request_response(request)


@router.patch(
    "/service-requests/{request_id}",
    response_model=ServiceRequestAdminResponse,
)
async def patch_admin_service_request(
    request_id: int,
    body: ServiceRequestPatch,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ServiceRequestAdminResponse:
    try:
        request = await service_request_service.patch_service_request(
            session,
            request_id=request_id,
            status=body.status,
            quoted_amount_minor=body.quoted_amount_minor,
            owner_note=body.owner_note,
        )
    except (ServiceRequestNotFound,) as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    except IllegalServiceRequestTransition as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="service_request_transition_not_allowed",
        ) from error
    return _admin_request_response(request)


def _user_response(user: User) -> UserAdminResponse:
    return UserAdminResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role,
        created_at=user.created_at,
    )


@router.get("/users", response_model=CursorPage[UserAdminResponse])
async def get_admin_users(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> CursorPage[UserAdminResponse]:
    try:
        users, next_cursor = await admin_users.list_users(
            session, limit=limit, cursor=cursor
        )
    except InvalidCursor as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_cursor"
        ) from error
    return CursorPage(
        items=[_user_response(user) for user in users], next_cursor=next_cursor
    )


@router.patch("/users/{user_id}/role", response_model=UserAdminResponse)
async def patch_admin_user_role(
    user_id: int,
    body: UserRolePatch,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserAdminResponse:
    try:
        user = await admin_users.set_user_role(session, user_id=user_id, role=body.role)
    except admin_users.UserNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    return _user_response(user)
