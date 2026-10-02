from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'paid', 'preparing', 'ready', 'completed', "
            "'cancelled')",
            name="valid_status",
        ),
        CheckConstraint(
            "fulfillment_type IN ('delivery', 'pickup')", name="valid_fulfillment_type"
        ),
        CheckConstraint("items_total_minor >= 0", name="items_total_nonnegative"),
        CheckConstraint("delivery_fee_minor >= 0", name="delivery_fee_nonnegative"),
        CheckConstraint("total_minor >= 0", name="total_nonnegative"),
        Index("ix_orders_user_id", "user_id"),
        UniqueConstraint(
            "user_id", "idempotency_key", name="uq_orders_user_id_idempotency_key"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    fulfillment_type: Mapped[str] = mapped_column(Text, nullable=False)
    fulfillment_date: Mapped[date] = mapped_column(Date, nullable=False)
    contact: Mapped[dict[str, str | None]] = mapped_column(JSONB, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    items_total_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    delivery_fee_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    total_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
