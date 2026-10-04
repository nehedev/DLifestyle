from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class MeResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str | None
    role: str


class UserAdminResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str | None
    role: str
    created_at: datetime


class UserRolePatch(BaseModel):
    role: Literal["user", "admin"]


__all__ = ["MeResponse", "UserAdminResponse", "UserRolePatch"]
