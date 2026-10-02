from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Identity,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        UniqueConstraint("order_id", "product_id", name="uq_order_items_order_product"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
