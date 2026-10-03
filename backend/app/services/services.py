from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cursors import decode_created_cursor, encode_created_cursor
from app.models import Service


class ServiceNotFound(Exception):
    pass


async def list_services(
    session: AsyncSession,
    *,
    limit: int,
    cursor: str | None,
) -> tuple[list[Service], str | None]:
    statement = select(Service)
    if cursor is not None:
        created_at, service_id = decode_created_cursor(cursor)
        statement = statement.where(
            or_(
                Service.created_at < created_at,
                and_(Service.created_at == created_at, Service.id < service_id),
            )
        )
    statement = statement.order_by(Service.created_at.desc(), Service.id.desc()).limit(
        limit + 1
    )
    services = list(await session.scalars(statement))
    has_next = len(services) > limit
    page = services[:limit]
    last_service = page[-1] if page else None
    next_cursor = (
        encode_created_cursor(last_service.created_at, last_service.id)
        if has_next and last_service is not None
        else None
    )
    return page, next_cursor


async def create_service(
    session: AsyncSession,
    *,
    name: str,
    description: str,
    is_active: bool,
    sort_order: int | None,
) -> Service:
    now = datetime.now(UTC)
    if sort_order is None:
        highest = await session.scalar(select(func.max(Service.sort_order)))
        sort_order = 1 if highest is None else highest + 1
    service = Service(
        name=name,
        description=description,
        is_active=is_active,
        sort_order=sort_order,
        created_at=now,
        updated_at=now,
    )
    session.add(service)
    await session.commit()
    return service


async def patch_service(
    session: AsyncSession,
    *,
    service_id: int,
    changes: dict[str, object],
) -> Service:
    service = await session.get(Service, service_id)
    if service is None:
        raise ServiceNotFound
    for field, value in changes.items():
        if value is not None:
            setattr(service, field, value)
    service.updated_at = datetime.now(UTC)
    await session.commit()
    return service


async def list_active_services(session: AsyncSession) -> list[Service]:
    statement = (
        select(Service)
        .where(Service.is_active.is_(True))
        .order_by(Service.sort_order, Service.id)
    )
    return list(await session.scalars(statement))
