from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

type NonEmptyString = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


class ShippingAddress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: NonEmptyString
    phone: Annotated[
        str,
        Field(pattern=r"^\+[1-9][0-9]{1,14}$", min_length=3, max_length=16),
    ]
    address_line_1: NonEmptyString
    city: NonEmptyString
    state: NonEmptyString
    country: Annotated[str, Field(pattern=r"^[A-Z]{2}$")]


class OrderItemInput(BaseModel):
    product_id: Annotated[int, Field(gt=0)]
    quantity: Annotated[int, Field(gt=0)]


class OrderCreate(BaseModel):
    items: list[OrderItemInput]
    shipping_address: ShippingAddress

    @model_validator(mode="after")
    def reject_duplicate_products(self) -> "OrderCreate":
        product_ids = [item.product_id for item in self.items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("duplicate_product_ids")
        return self


class OrderItemResponse(BaseModel):
    product_id: int
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
    total_minor: int
    currency: str
    shipping_address: ShippingAddress
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemResponse]


class OrderDetailResponse(OrderResponse):
    payments: list[PaymentSummary]


class CursorPage[T](BaseModel):
    items: list[T]
    next_cursor: str | None
