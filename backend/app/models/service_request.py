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
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ServiceRequest(Base):
    __tablename__ = "service_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('requested', 'contacted', 'confirmed', 'completed', "
            "'cancelled')",
            name="valid_status",
        ),
        CheckConstraint(
            "quoted_amount_minor IS NULL OR quoted_amount_minor >= 0",
            name="quoted_amount_minor_nonnegative",
        ),
        Index("ix_service_requests_user_id", "user_id"),
        Index("ix_service_requests_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    service_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("services.id"), nullable=False
    )
    preferred_date: Mapped[date | None] = mapped_column(Date)
    location: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    contact_phone: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    quoted_amount_minor: Mapped[int | None] = mapped_column(Integer)
    owner_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
