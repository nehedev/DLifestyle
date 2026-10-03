from pydantic import BaseModel


class StorePublic(BaseModel):
    delivery_fee_minor: int
    order_cutoff_time: str
    max_advance_days: int
    currency: str
    timezone: str
