from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class MeResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str | None
    role: str


class GoogleSignInRequest(BaseModel):
    code: str
    # Native apps run the auth-code flow against a registered deep-link redirect
    # and must present the same value at the token exchange. The web popup flow
    # omits it and falls back to Google's "postmessage".
    redirect_uri: str | None = None


class GoogleSignInResponse(BaseModel):
    id_token: str
    expires_at: int
    picture: str | None
    user: MeResponse


class UserAdminResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str | None
    role: str
    created_at: datetime


class UserRolePatch(BaseModel):
    role: Literal["user", "admin"]


__all__ = [
    "GoogleSignInRequest",
    "GoogleSignInResponse",
    "MeResponse",
    "UserAdminResponse",
    "UserRolePatch",
]
