from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from geodom_backend.db.base import Base

if TYPE_CHECKING:
    from .apartment import Apartment

class District(Base):
    __tablename__ = "districts"

    __table_args__ = (
        UniqueConstraint(
            "source",
            "source_id",
            name="uq_districts_source_source_id"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        index=True,
        nullable=False
    )

    source: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True
    )

    source_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    center_latitude: Mapped[Decimal | None] = mapped_column(
        Numeric(
            precision=9,
            scale=6
        ),
        nullable=True
    )

    center_longitude: Mapped[Decimal | None] = mapped_column(
        Numeric(
            precision=10,
            scale=6
        ),
        nullable=True
    )

    geometry: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    apartments: Mapped[list[Apartment]] = relationship(
        back_populates="district"
    )
