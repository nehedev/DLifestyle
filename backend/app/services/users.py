import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import User
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


class InvalidUserClaims(Exception):
    pass


class EmailConflict(Exception):
    pass


def _required_claim(claims: Mapping[str, Any], claim_name: str) -> str:
    value = claims.get(claim_name)
    if not isinstance(value, str) or not value.strip():
        raise InvalidUserClaims
    return value


def _user_values(claims: Mapping[str, Any]) -> dict[str, str | None]:
    auth0_sub = _required_claim(claims, "sub")
    email = _required_claim(claims, settings.auth0_email_claim)
    first_name = _required_claim(claims, settings.auth0_first_name_claim)
    raw_last_name = claims.get(settings.auth0_last_name_claim)
    if raw_last_name is None or raw_last_name == "":
        last_name = None
    elif isinstance(raw_last_name, str):
        last_name = raw_last_name if raw_last_name.strip() else None
    else:
        raise InvalidUserClaims

    return {
        "auth0_sub": auth0_sub,
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
    }


async def _ensure_email_available(
    session: AsyncSession,
    email: str,
    *,
    exclude_user_id: int | None = None,
) -> None:
    statement = select(User.id).where(User.email == email)
    if exclude_user_id is not None:
        statement = statement.where(User.id != exclude_user_id)
    if await session.scalar(statement) is not None:
        raise EmailConflict


async def _sync_existing_user(
    session: AsyncSession,
    user: User,
    values: dict[str, str | None],
) -> User:
    email = values["email"]
    assert isinstance(email, str)
    await _ensure_email_available(session, email, exclude_user_id=user.id)

    changed = any(
        getattr(user, field) != value
        for field, value in values.items()
        if field != "auth0_sub"
    )
    if not changed:
        return user

    for field, value in values.items():
        if field != "auth0_sub":
            setattr(user, field, value)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        try:
            await _ensure_email_available(session, email, exclude_user_id=user.id)
        except EmailConflict:
            raise
        raise error
    return user


async def resolve_current_user(
    session: AsyncSession,
    claims: Mapping[str, Any],
) -> User:
    values = _user_values(claims)
    auth0_sub = values["auth0_sub"]
    email = values["email"]
    assert isinstance(auth0_sub, str)
    assert isinstance(email, str)

    user = await session.scalar(select(User).where(User.auth0_sub == auth0_sub))
    if user is not None:
        return await _sync_existing_user(session, user, values)

    statement = (
        pg_insert(User)
        .values(**values, created_at=datetime.now(UTC))
        .on_conflict_do_nothing()
        .returning(User)
    )
    try:
        inserted_user = await session.scalar(statement)
    except IntegrityError as error:
        await session.rollback()
        try:
            await _ensure_email_available(session, email)
        except EmailConflict:
            raise
        raise error

    if inserted_user is not None:
        await session.commit()
        logger.info("user.provisioned")
        celery_app.send_task("send_welcome_email", args=[inserted_user.id])
        return inserted_user

    # The email check deliberately happens after the insert, not before it.
    # Checking first races: a concurrent request can commit its own new row
    # between the check and this insert, and the loser would then report an
    # email conflict against the very row it was racing to create.
    await session.rollback()
    user = await session.scalar(select(User).where(User.auth0_sub == auth0_sub))
    if user is not None:
        return await _sync_existing_user(session, user, values)
    await _ensure_email_available(session, email)
    raise RuntimeError("Auth0 subject conflict did not resolve to a user")
