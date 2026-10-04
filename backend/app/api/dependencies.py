from dataclasses import dataclass
from logging import getLogger
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import google
from app.core.google import AuthProviderUnavailable, InvalidAccessToken
from app.db.session import get_session
from app.models import User
from app.services.users import EmailConflict, InvalidUserClaims, resolve_current_user

bearer_scheme = HTTPBearer(auto_error=False)
logger = getLogger(__name__)

ADMIN_ROLE = "admin"


@dataclass(frozen=True, slots=True)
class CurrentUser:
    user: User

    @property
    def is_admin(self) -> bool:
        return self.user.role == ADMIN_ROLE


def _invalid_token() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid_token",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CurrentUser:
    if credentials is None:
        raise _invalid_token()

    try:
        claims = await google.token_verifier.verify(credentials.credentials)
    except InvalidAccessToken as error:
        raise _invalid_token() from error
    except AuthProviderUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="auth_provider_unavailable",
        ) from error

    try:
        user = await resolve_current_user(session, claims)
    except InvalidUserClaims as error:
        raise _invalid_token() from error
    except EmailConflict as error:
        logger.error("user.email_conflict")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="account_exists_use_existing_sign_in",
        ) from error

    return CurrentUser(user=user)


async def get_admin_user(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin_required",
        )
    return current_user
