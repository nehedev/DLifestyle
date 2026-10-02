from sqlalchemy import BigInteger, Boolean, CheckConstraint, Identity, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price_minor >= 0", name="price_minor_nonnegative"),
        CheckConstraint("stock_quantity >= 0", name="stock_quantity_nonnegative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
