from datetime import time
from typing import Annotated

from pydantic import BaseModel, Field


class StorePublic(BaseModel):
    delivery_fee_minor: int
    order_cutoff_time: str
    max_advance_days: int
    currency: str
    timezone: str


class StoreSettingsPut(BaseModel):
    delivery_fee_minor: Annotated[int, Field(ge=0)]
    order_cutoff_time: time
    max_advance_days: Annotated[int, Field(ge=0)]
