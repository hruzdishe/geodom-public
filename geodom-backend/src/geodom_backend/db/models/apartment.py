from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from geodom_backend.apartments.enums import (
    ApartmentDealType,
    ApartmentOrigin,
    ApartmentStatus,
    RentPeriod,
)
from geodom_backend.db.base import Base

if TYPE_CHECKING:
    from .apartment_features import ApartmentFeatures
    from .apartment_photo import ApartmentPhoto
    from .district import District
    from .user import User

class Apartment(Base):
    __tablename__ = "apartments"

    __table_args__ = (
        UniqueConstraint(
            "source",
            "source_id",
            name="uq_apartments_source_source_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    dataset_id: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True
    )

    external_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        index=True,
        nullable=True,
    )

    district_id: Mapped[int] = mapped_column(
        ForeignKey(
            "districts.id",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=14,
            scale=2,
        ),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        default="RUB",
        server_default="RUB",
        nullable=False,
    )

    deal_type: Mapped[ApartmentDealType] = mapped_column(
        Enum(
            ApartmentDealType,
            name="apartment_deal_type",
            values_callable=lambda enum: [
                item.value for item in enum
            ],
        ),
        nullable=False,
        index=True
    )

    rent_period: Mapped[RentPeriod | None] = mapped_column(
        Enum(
            RentPeriod,
            name="rent_period",
            values_callable=lambda enum: [
                item.value for item in enum
            ]
        ),
        nullable=True
    )

    area: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=8,
            scale=2,
        ),
        nullable=False,
    )

    rooms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    floor: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    total_floors: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    building_year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    address: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    house_number: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    latitude: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=9,
            scale=6,
        ),
        nullable=False,
    )

    longitude: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=10,
            scale=6,
        ),
        nullable=False,
    )

    coordinate_method: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    district_assignment_method: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    complex_source_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    complex_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    complex_source_url: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )

    market_type: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    offer_type: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    origin: Mapped[ApartmentOrigin] = mapped_column(
        Enum(
            ApartmentOrigin,
            name="apartment_origin",
            values_callable=lambda enum: [
                item.value for item in enum
            ],
        ),
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    source_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    source_url: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )

    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    collected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    raw_sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    is_demo: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )

    status: Mapped[ApartmentStatus] = mapped_column(
        Enum(
            ApartmentStatus,
            name="apartment_status",
            values_callable=lambda enum: [
                item.value for item in enum
            ],
        ),
        default=ApartmentStatus.PUBLISHED,
        server_default=ApartmentStatus.PUBLISHED.value,
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    owner: Mapped[User | None] = relationship(
        back_populates="apartments",
    )

    district: Mapped[District] = relationship(
        back_populates="apartments",
    )

    photos: Mapped[list[ApartmentPhoto]] = relationship(
        back_populates="apartment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ApartmentPhoto.position",
    )

    features: Mapped[ApartmentFeatures | None] = relationship(
        back_populates="apartment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False
    )
