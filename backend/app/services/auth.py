from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import google
from app.core.google import InvalidAccessToken
from app.models import User
from app.services.users import resolve_current_user


@dataclass(frozen=True, slots=True)
class GoogleSignIn:
    id_token: str
    expires_at: int
    picture: str | None
    user: User


async def sign_in_with_google_code(session: AsyncSession, code: str) -> GoogleSignIn:
    """Exchange a Google authorization code and provision the local user.

    The code is exchanged server-side with the client secret, then the returned
    ID token is verified against Google's JWKS before any session is issued.
    """
    id_token = await google.code_exchanger.exchange(code)
    claims: Mapping[str, Any] = await google.token_verifier.verify(id_token)
    user = await resolve_current_user(session, claims)

    expires_at = claims.get("exp")
    if not isinstance(expires_at, int):
        raise InvalidAccessToken
    picture = claims.get("picture")

    return GoogleSignIn(
        id_token=id_token,
        expires_at=expires_at,
        picture=picture if isinstance(picture, str) else None,
        user=user,
    )
