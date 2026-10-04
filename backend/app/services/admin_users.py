"""Admin reads and role management for local users."""

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cursors import decode_created_cursor, encode_created_cursor
from app.models import User


class UserNotFound(Exception):
    pass


async def list_users(
    session: AsyncSession,
    *,
    limit: int,
    cursor: str | None,
) -> tuple[list[User], str | None]:
    statement = select(User)
    if cursor is not None:
        created_at, user_id = decode_created_cursor(cursor)
        statement = statement.where(
            or_(
                User.created_at < created_at,
                and_(User.created_at == created_at, User.id < user_id),
            )
        )
    statement = statement.order_by(User.created_at.desc(), User.id.desc()).limit(
        limit + 1
    )
    users = list(await session.scalars(statement))
    has_next = len(users) > limit
    page = users[:limit]
    last_user = page[-1] if page else None
    next_cursor = (
        encode_created_cursor(last_user.created_at, last_user.id)
        if has_next and last_user is not None
        else None
    )
    return page, next_cursor


async def set_user_role(
    session: AsyncSession,
    *,
    user_id: int,
    role: str,
) -> User:
    transition = await session.execute(
        update(User).where(User.id == user_id).values(role=role).returning(User.id)
    )
    if transition.scalar_one_or_none() != user_id:
        await session.rollback()
        raise UserNotFound
    await session.commit()
    user = await session.get(User, user_id)
    if user is None:
        raise UserNotFound
    return user
