from pydantic import BaseModel


class MenuItemPublic(BaseModel):
    id: int
    name: str
    description: str | None
    price_minor: int
    is_sold_out: bool
    weekdays: list[int]
