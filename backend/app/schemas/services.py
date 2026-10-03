from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

type ServiceName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
type ServiceDescription = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=2000)
]


class ServicePublic(BaseModel):
    id: int
    name: str
    description: str


class ServiceAdmin(ServicePublic):
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class ServiceCreate(BaseModel):
    name: ServiceName
    description: ServiceDescription
    is_active: bool = True
    sort_order: int | None = None


class ServicePatch(BaseModel):
    name: ServiceName | None = None
    description: ServiceDescription | None = None
    is_active: bool | None = None
    sort_order: int | None = None
