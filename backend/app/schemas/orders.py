from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.schemas.base import CursorPage

type NonEmptyText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
type OptionalAddress = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
type PhoneNumber = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=16),
    Field(pattern=r"^\+[1-9][0-9]{1,14}$"),
]
type OrderNotes = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=1000)
]


class OrderContact(BaseModel):
    name: NonEmptyText
    phone: PhoneNumber
    address: OptionalAddress | None = None


class OrderItemInput(BaseModel):
    menu_item_id: Annotated[int, Field(gt=0)]
    quantity: Annotated[int, Field(gt=0)]


class OrderCreate(BaseModel):
    items: Annotated[list[OrderItemInput], Field(min_length=1)]
    fulfillment_type: Annotated[str, Field(pattern=r"^(delivery|pickup)$")]
    fulfillment_date: date
    contact: OrderContact
    notes: OrderNotes | None = None

    @model_validator(mode="after")
    def check_items_and_contact(self) -> "OrderCreate":
        menu_item_ids = [item.menu_item_id for item in self.items]
        if len(menu_item_ids) != len(set(menu_item_ids)):
            raise ValueError("duplicate_menu_item_ids")
        if self.fulfillment_type == "delivery" and self.contact.address is None:
            raise ValueError("address_required_for_delivery")
        return self


class OrderItemResponse(BaseModel):
    name: str
    quantity: int
    unit_price_minor: int


class PaymentSummary(BaseModel):
    id: int
    status: str
    amount_minor: int
    currency: str


class OrderResponse(BaseModel):
    id: int
    status: str
    fulfillment_type: str
    fulfillment_date: date
    contact: OrderContact
    notes: str | None
    items_total_minor: int
    delivery_fee_minor: int
    total_minor: int
    currency: str
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemResponse]


class OrderDetailResponse(OrderResponse):
    payments: list[PaymentSummary]


__all__ = [
    "CursorPage",
    "OrderContact",
    "OrderCreate",
    "OrderDetailResponse",
    "OrderItemInput",
    "OrderItemResponse",
    "OrderResponse",
    "PaymentSummary",
]
