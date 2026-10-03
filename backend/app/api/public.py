from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.models import StoreSettings
from app.schemas.base import ItemsPage
from app.schemas.menu import MenuItemPublic
from app.schemas.services import ServicePublic
from app.schemas.store import StorePublic
from app.services.menu import list_active_menu_items
from app.services.services import list_active_services
from app.services.store_settings import get_store_settings

router = APIRouter()


@router.get("/menu", response_model=ItemsPage[MenuItemPublic])
async def get_menu(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ItemsPage[MenuItemPublic]:
    menu_items = await list_active_menu_items(session)
    return ItemsPage(
        items=[
            MenuItemPublic(
                id=menu_item.id,
                name=menu_item.name,
                description=menu_item.description,
                price_minor=menu_item.price_minor,
                is_sold_out=menu_item.is_sold_out,
                weekdays=[day.weekday for day in menu_item.days],
            )
            for menu_item in menu_items
        ]
    )


@router.get("/services", response_model=ItemsPage[ServicePublic])
async def get_services(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ItemsPage[ServicePublic]:
    services = await list_active_services(session)
    return ItemsPage(
        items=[
            ServicePublic(
                id=service.id,
                name=service.name,
                description=service.description,
            )
            for service in services
        ]
    )


@router.get("/store", response_model=StorePublic)
async def get_store(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StorePublic:
    store_settings: StoreSettings | None = await get_store_settings(session)
    if store_settings is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="store_not_configured",
        )
    return StorePublic(
        delivery_fee_minor=store_settings.delivery_fee_minor,
        order_cutoff_time=store_settings.order_cutoff_time.strftime("%H:%M"),
        max_advance_days=store_settings.max_advance_days,
        currency=settings.currency,
        timezone=settings.business_timezone,
    )
