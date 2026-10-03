from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Service


async def list_active_services(session: AsyncSession) -> list[Service]:
    statement = (
        select(Service)
        .where(Service.is_active.is_(True))
        .order_by(Service.sort_order, Service.id)
    )
    return list(await session.scalars(statement))
