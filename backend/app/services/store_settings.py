from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import StoreSettings
from app.models.store_settings import SINGLETON_STORE_SETTINGS_ID


class StoreNotConfigured(Exception):
    pass


def business_timezone() -> ZoneInfo:
    return ZoneInfo(settings.business_timezone)


def cutoff_instant(
    store_settings: StoreSettings,
    *,
    fulfillment_date: date,
) -> datetime:
    return datetime.combine(
        fulfillment_date,
        store_settings.order_cutoff_time,
        business_timezone(),
    )


async def get_store_settings(
    session: AsyncSession,
) -> StoreSettings | None:
    return await session.get(StoreSettings, SINGLETON_STORE_SETTINGS_ID)


async def require_store_settings(session: AsyncSession) -> StoreSettings:
    store_settings = await get_store_settings(session)
    if store_settings is None:
        raise StoreNotConfigured
    return store_settings


def is_ordering_open(
    store_settings: StoreSettings,
    *,
    fulfillment_date: date,
    now: datetime,
) -> bool:
    today = now.astimezone(business_timezone()).date()
    if fulfillment_date < today:
        return False
    if fulfillment_date > today + timedelta(days=store_settings.max_advance_days):
        return False
    return now < cutoff_instant(store_settings, fulfillment_date=fulfillment_date)


def has_cutoff_passed(
    store_settings: StoreSettings,
    *,
    fulfillment_date: date,
    now: datetime,
) -> bool:
    return now >= cutoff_instant(store_settings, fulfillment_date=fulfillment_date)
