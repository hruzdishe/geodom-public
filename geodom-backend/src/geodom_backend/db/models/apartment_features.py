from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from geodom_backend.apartments.enums import ApartmentFeatureStatus
from geodom_backend.db.base import Base

if TYPE_CHECKING:
    from .apartment import Apartment

class ApartmentFeatures(Base):
    __tablename__ = "apartment_features"

    apartment_id: Mapped[int] = mapped_column(
        ForeignKey(
            "apartments.id",
            ondelete="CASCADE"
        ),
        primary_key=True
    )

    status: Mapped[ApartmentFeatureStatus] = mapped_column(
        Enum(
            ApartmentFeatureStatus,
            name="apartment_feature_status",
            values_callable=lambda enum: [
                item.value for item in enum
            ]
        ),
        nullable=False,
        default=ApartmentFeatureStatus.PENDING,
        server_default=ApartmentFeatureStatus.PENDING.value,
        index=True
    )

    schools_1km: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    kindergartens_1km: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    parks_1km: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    shops_1km: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    transport_stops_1km: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    nearest_school_m: Mapped[Decimal | None] = mapped_column(
        Numeric(
            precision=10,
            scale=2
        ),
        nullable=True
    )

    nearest_kindergarten_m: Mapped[Decimal | None] = mapped_column(
        Numeric(
            precision=10,
            scale=2
        ),
        nullable=True
    )

    nearest_park_m: Mapped[Decimal | None] = mapped_column(
        Numeric(
            precision=10,
            scale=2
        ),
        nullable=True
    )

    nearest_transport_m: Mapped[Decimal | None] = mapped_column(
        Numeric(
            precision=10,
            scale=2
        ),
        nullable=True
    )

    feature_version: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True
    )

    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    computed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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

    apartment: Mapped[Apartment] = relationship(
        back_populates="features"
    )
