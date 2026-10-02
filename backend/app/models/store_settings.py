from datetime import datetime, time

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Identity,
    Integer,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SINGLETON_STORE_SETTINGS_ID = 1


class StoreSettings(Base):
    __tablename__ = "store_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="singleton_row"),
        CheckConstraint(
            "delivery_fee_minor >= 0", name="delivery_fee_minor_nonnegative"
        ),
        CheckConstraint("max_advance_days >= 0", name="max_advance_days_nonnegative"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(start=1, increment=1), primary_key=True
    )
    delivery_fee_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    order_cutoff_time: Mapped[time] = mapped_column(Time, nullable=False)
    max_advance_days: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
