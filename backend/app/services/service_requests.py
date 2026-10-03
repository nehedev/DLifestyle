import logging
from datetime import UTC, date, datetime

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cursors import decode_created_cursor, encode_created_cursor
from app.models import Service, ServiceRequest, User
from app.services.store_settings import business_timezone
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

CUSTOMER_CANCELLABLE = ("requested", "contacted")
ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "requested": ("contacted", "cancelled"),
    "contacted": ("confirmed", "cancelled"),
    "confirmed": ("completed", "cancelled"),
    "completed": (),
    "cancelled": (),
}


class ServiceRequestNotFound(Exception):
    pass


class ServiceNotFound(Exception):
    pass


class ServiceNotActive(Exception):
    pass


class PreferredDateInThePast(Exception):
    pass


class IllegalServiceRequestTransition(Exception):
    pass


def business_today() -> date:
    return datetime.now(UTC).astimezone(business_timezone()).date()


async def create_service_request(
    session: AsyncSession,
    *,
    user: User,
    service_id: int,
    preferred_date: date | None,
    location: str,
    details: str,
    contact_phone: str,
) -> ServiceRequest:
    service = await session.get(Service, service_id)
    if service is None:
        raise ServiceNotFound
    if not service.is_active:
        raise ServiceNotActive
    if preferred_date is not None and preferred_date < business_today():
        raise PreferredDateInThePast

    now = datetime.now(UTC)
    request = ServiceRequest(
        user_id=user.id,
        service_id=service_id,
        preferred_date=preferred_date,
        location=location,
        details=details,
        contact_phone=contact_phone,
        status="requested",
        created_at=now,
        updated_at=now,
    )
    session.add(request)
    await session.commit()
    logger.info("service_request.created")
    celery_app.send_task("send_request_received_email", args=[request.id])
    celery_app.send_task("send_new_service_request_email", args=[request.id])
    return request


async def list_service_requests(
    session: AsyncSession,
    *,
    user_id: int | None,
    status: str | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[ServiceRequest], str | None]:
    """List requests; ``user_id`` of ``None`` means every user's requests."""
    statement = select(ServiceRequest)
    if user_id is not None:
        statement = statement.where(ServiceRequest.user_id == user_id)
    if status is not None:
        statement = statement.where(ServiceRequest.status == status)
    if cursor is not None:
        created_at, request_id = decode_created_cursor(cursor)
        statement = statement.where(
            or_(
                ServiceRequest.created_at < created_at,
                and_(
                    ServiceRequest.created_at == created_at,
                    ServiceRequest.id < request_id,
                ),
            )
        )
    statement = statement.order_by(
        ServiceRequest.created_at.desc(), ServiceRequest.id.desc()
    ).limit(limit + 1)
    requests = list(await session.scalars(statement))
    has_next = len(requests) > limit
    page = requests[:limit]
    last_request = page[-1] if page else None
    next_cursor = (
        encode_created_cursor(last_request.created_at, last_request.id)
        if has_next and last_request is not None
        else None
    )
    return page, next_cursor


async def get_service_request(
    session: AsyncSession,
    *,
    request_id: int,
    user_id: int | None,
) -> ServiceRequest | None:
    statement = select(ServiceRequest).where(ServiceRequest.id == request_id)
    if user_id is not None:
        statement = statement.where(ServiceRequest.user_id == user_id)
    return await session.scalar(statement)


async def cancel_service_request(
    session: AsyncSession,
    *,
    request_id: int,
    user_id: int,
) -> ServiceRequest:
    transition = await session.execute(
        update(ServiceRequest)
        .where(
            ServiceRequest.id == request_id,
            ServiceRequest.user_id == user_id,
            ServiceRequest.status.in_(CUSTOMER_CANCELLABLE),
        )
        .values(status="cancelled", updated_at=datetime.now(UTC))
        .returning(ServiceRequest.id)
    )
    if transition.scalar_one_or_none() != request_id:
        await session.rollback()
        request = await get_service_request(
            session, request_id=request_id, user_id=user_id
        )
        if request is None:
            raise ServiceRequestNotFound
        raise IllegalServiceRequestTransition
    await session.commit()
    request = await session.get(ServiceRequest, request_id)
    if request is None:
        raise ServiceRequestNotFound
    return request


async def patch_service_request(
    session: AsyncSession,
    *,
    request_id: int,
    status: str | None,
    quoted_amount_minor: int | None,
    owner_note: str | None,
) -> ServiceRequest:
    request = await session.get(ServiceRequest, request_id)
    if request is None:
        raise ServiceRequestNotFound

    now = datetime.now(UTC)
    if status is not None:
        if status not in ALLOWED_TRANSITIONS.get(request.status, ()):
            raise IllegalServiceRequestTransition
        transition = await session.execute(
            update(ServiceRequest)
            .where(
                ServiceRequest.id == request_id,
                ServiceRequest.status == request.status,
            )
            .values(status=status, updated_at=now)
            .returning(ServiceRequest.id)
        )
        if transition.scalar_one_or_none() != request_id:
            await session.rollback()
            raise IllegalServiceRequestTransition

    other_changes = {
        column: value
        for column, value in (
            ("quoted_amount_minor", quoted_amount_minor),
            ("owner_note", owner_note),
        )
        if value is not None
    }
    if other_changes:
        await session.execute(
            update(ServiceRequest)
            .where(ServiceRequest.id == request_id)
            .values(**other_changes, updated_at=now)
        )

    await session.commit()
    updated = await session.get(ServiceRequest, request_id)
    if updated is None:
        raise ServiceRequestNotFound
    return updated
