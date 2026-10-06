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
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        CheckConstraint("kind IN ('food', 'service')", name="valid_kind"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint(
            "(kind = 'food' AND menu_item_id IS NOT NULL "
            "AND service_id IS NULL AND preferred_date IS NULL) OR "
            "(kind = 'service' AND service_id IS NOT NULL "
            "AND menu_item_id IS NULL)",
            name="target_matches_kind",
        ),
        Index("ix_cart_items_user_id", "user_id"),
        Index(
            "uq_cart_items_food",
            "user_id",
            "menu_item_id",
            unique=True,
            postgresql_where=text("kind = 'food'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    menu_item_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("menu_items.id"), nullable=True
    )
    service_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("services.id"), nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    preferred_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
