from logging import getLogger
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import auth0
from app.core.auth0 import AuthProviderUnavailable, InvalidAccessToken
from app.db.session import get_session
from app.models import User
from app.services.users import EmailConflict, InvalidUserClaims, resolve_current_user

bearer_scheme = HTTPBearer(auto_error=False)
logger = getLogger(__name__)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = await auth0.token_verifier.verify(credentials.credentials)
    except InvalidAccessToken as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    except AuthProviderUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="auth_provider_unavailable",
        ) from error

    try:
        return await resolve_current_user(session, claims)
    except InvalidUserClaims as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    except EmailConflict as error:
        logger.error("user.email_conflict")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="account_exists_use_existing_sign_in",
        ) from error
