from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.menu_item import MenuItem


class MenuItemDay(Base):
    __tablename__ = "menu_item_days"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 1 AND 7", name="weekday_iso_range"),
    )

    menu_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("menu_items.id", ondelete="CASCADE"),
        primary_key=True,
    )
    weekday: Mapped[int] = mapped_column(
        SmallInteger, primary_key=True, autoincrement=False
    )
    menu_item: Mapped["MenuItem"] = relationship(back_populates="days")
