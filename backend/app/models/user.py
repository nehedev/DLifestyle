from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Identity, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    auth0_sub: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    last_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
