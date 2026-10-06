from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CartItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["food", "service"]
    menu_item_id: int | None = None
    service_id: int | None = None
    quantity: int = Field(ge=1)
    preferred_date: date | None = None

    @model_validator(mode="after")
    def check_target(self) -> Self:
        if self.kind == "food":
            if (
                self.menu_item_id is None
                or self.service_id is not None
                or self.preferred_date is not None
            ):
                raise ValueError(
                    "food lines need menu_item_id and no service_id or preferred_date"
                )
        else:
            if self.service_id is None or self.menu_item_id is not None:
                raise ValueError("service lines need service_id and no menu_item_id")
            if self.quantity != 1:
                raise ValueError("service lines always have quantity 1")
        return self


class CartReplaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CartItemInput]


class CartItemResponse(BaseModel):
    kind: Literal["food", "service"]
    menu_item_id: int | None
    service_id: int | None
    quantity: int
    preferred_date: date | None


class CartResponse(BaseModel):
    items: list[CartItemResponse]


__all__ = [
    "CartItemInput",
    "CartItemResponse",
    "CartReplaceRequest",
    "CartResponse",
]
