from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

type LocationText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
type DetailsText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]
type PhoneNumber = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=16),
    Field(pattern=r"^\+[1-9][0-9]{1,14}$"),
]
type OwnerNote = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=2000)
]
type QuotedAmountMinor = Annotated[int, Field(ge=0)]
type ServiceRequestStatus = Annotated[
    str,
    Field(pattern=r"^(requested|contacted|confirmed|completed|cancelled)$"),
]


class ServiceRequestCreate(BaseModel):
    service_id: Annotated[int, Field(gt=0)]
    preferred_date: date | None = None
    location: LocationText
    details: DetailsText
    contact_phone: PhoneNumber


class ServiceRequestPatch(BaseModel):
    status: ServiceRequestStatus | None = None
    quoted_amount_minor: QuotedAmountMinor | None = None
    owner_note: OwnerNote | None = None


class ServiceRequestResponse(BaseModel):
    id: int
    service_id: int
    preferred_date: date | None
    location: str
    details: str
    contact_phone: str
    status: str
    quoted_amount_minor: int | None
    owner_note: str | None
    created_at: datetime
    updated_at: datetime


class ServiceRequestAdminResponse(ServiceRequestResponse):
    user_id: int
