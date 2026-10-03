from collections.abc import Mapping
from dataclasses import dataclass
from logging import getLogger
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import auth0
from app.core.auth0 import AuthProviderUnavailable, InvalidAccessToken
from app.core.config import settings
from app.db.session import get_session
from app.models import User
from app.services.users import EmailConflict, InvalidUserClaims, resolve_current_user

bearer_scheme = HTTPBearer(auto_error=False)
logger = getLogger(__name__)

OWNER_ROLE = "owner"


@dataclass(frozen=True, slots=True)
class CurrentUser:
    user: User
    roles: frozenset[str]

    @property
    def is_owner(self) -> bool:
        return OWNER_ROLE in self.roles


def _invalid_token() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid_token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def roles_from_claims(claims: Mapping[str, Any]) -> frozenset[str]:
    raw_roles = claims.get(settings.auth0_roles_claim)
    if not isinstance(raw_roles, list):
        return frozenset()
    return frozenset(role for role in raw_roles if isinstance(role, str) and role)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CurrentUser:
    if credentials is None:
        raise _invalid_token()

    try:
        claims = await auth0.token_verifier.verify(credentials.credentials)
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

    return CurrentUser(user=user, roles=roles_from_claims(claims))


async def get_owner_user(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    if not current_user.is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="owner_required",
        )
    return current_user
