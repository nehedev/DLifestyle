from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
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


async def put_store_settings(
    session: AsyncSession,
    *,
    delivery_fee_minor: int,
    order_cutoff_time: time,
    max_advance_days: int,
) -> StoreSettings:
    now = datetime.now(UTC)
    store_settings = await session.get(
        StoreSettings, SINGLETON_STORE_SETTINGS_ID, with_for_update=True
    )
    creating = store_settings is None
    if creating:
        store_settings = StoreSettings(id=SINGLETON_STORE_SETTINGS_ID)
        session.add(store_settings)
    _apply(
        store_settings,
        delivery_fee_minor=delivery_fee_minor,
        order_cutoff_time=order_cutoff_time,
        max_advance_days=max_advance_days,
        updated_at=now,
    )
    try:
        await session.commit()
    except IntegrityError:
        if not creating:
            raise
        await session.rollback()
        store_settings = await session.get(
            StoreSettings, SINGLETON_STORE_SETTINGS_ID, with_for_update=True
        )
        if store_settings is None:
            raise
        _apply(
            store_settings,
            delivery_fee_minor=delivery_fee_minor,
            order_cutoff_time=order_cutoff_time,
            max_advance_days=max_advance_days,
            updated_at=now,
        )
        await session.commit()
    return store_settings


def _apply(
    store_settings: StoreSettings,
    *,
    delivery_fee_minor: int,
    order_cutoff_time: time,
    max_advance_days: int,
    updated_at: datetime,
) -> None:
    store_settings.delivery_fee_minor = delivery_fee_minor
    store_settings.order_cutoff_time = order_cutoff_time
    store_settings.max_advance_days = max_advance_days
    store_settings.updated_at = updated_at


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
