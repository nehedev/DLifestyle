from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

type MenuItemName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
type MenuItemDescription = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=2000)
]
type MenuItemCategory = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
type MenuItemImageUrl = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2048)
]
type MenuItemImageAlt = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
type PriceMinor = Annotated[int, Field(ge=0)]
type Weekdays = Annotated[list[Annotated[int, Field(ge=1, le=7)]], Field(min_length=1)]


class MenuItemPublic(BaseModel):
    id: int
    name: str
    description: str | None
    category: str
    image_url: str | None
    image_alt: str | None
    price_minor: int
    is_sold_out: bool
    weekdays: list[int]


class MenuItemAdmin(MenuItemPublic):
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MenuItemCreate(BaseModel):
    name: MenuItemName
    description: MenuItemDescription | None = None
    category: MenuItemCategory
    image_url: MenuItemImageUrl | None = None
    image_alt: MenuItemImageAlt | None = None
    price_minor: PriceMinor
    weekdays: Weekdays
    is_active: bool = True
    is_sold_out: bool = False


class MenuItemPatch(BaseModel):
    name: MenuItemName | None = None
    description: MenuItemDescription | None = None
    category: MenuItemCategory | None = None
    image_url: MenuItemImageUrl | None = None
    image_alt: MenuItemImageAlt | None = None
    price_minor: PriceMinor | None = None
    weekdays: Weekdays | None = None
    is_active: bool | None = None
    is_sold_out: bool | None = None
