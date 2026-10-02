from pydantic import BaseModel


class ProductResponse(BaseModel):
    id: int
    name: str
    price_minor: int
    stock_quantity: int
    is_active: bool
