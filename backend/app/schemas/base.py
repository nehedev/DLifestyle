from pydantic import BaseModel


class ItemsPage[T](BaseModel):
    items: list[T]


class CursorPage[T](ItemsPage[T]):
    next_cursor: str | None
