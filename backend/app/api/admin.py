from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_owner_user
from app.core.config import settings
from app.core.cursors import InvalidCursor
from app.db.session import get_session
from app.models import MenuItem, Service, StoreSettings
from app.schemas.base import CursorPage
from app.schemas.menu import MenuItemAdmin, MenuItemCreate, MenuItemPatch
from app.schemas.services import ServiceAdmin, ServiceCreate, ServicePatch
from app.schemas.store import StorePublic, StoreSettingsPut
from app.services import menu as menu_service
from app.services import services as services_service
from app.services.store_settings import get_store_settings, put_store_settings

router = APIRouter(prefix="/admin", dependencies=[Depends(get_owner_user)])


def _menu_item_response(menu_item: MenuItem) -> MenuItemAdmin:
    return MenuItemAdmin(
        id=menu_item.id,
        name=menu_item.name,
        description=menu_item.description,
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
