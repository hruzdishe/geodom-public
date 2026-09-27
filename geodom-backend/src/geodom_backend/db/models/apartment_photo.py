from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from geodom_backend.db.base import Base

if TYPE_CHECKING:
    from .apartment import Apartment


class ApartmentPhoto(Base):
    __tablename__ = "apartment_photos"

    __table_args__ = (
        UniqueConstraint(
            "apartment_id",
            "position",
            name="uq_apartment_photos_apartment_position",
        ),
        UniqueConstraint(
            "bucket",
            "storage_key",
            name="uq_apartment_photos_bucket_storage_key",
        ),
        Index(
            "uq_apartment_photos_cover_per_apartment",
            "apartment_id",
            unique=True,
            postgresql_where=text("is_cover = true"),
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    external_id: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
    )

    apartment_id: Mapped[int] = mapped_column(
        ForeignKey(
            "apartments.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    bucket: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    storage_key: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    local_path: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True
    )

    source: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    source_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )

    listing_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    is_cover: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    width: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    height: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    mime_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    original_sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    rights_status: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    attribution: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )

    publication_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    image_kind: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    apartment: Mapped[Apartment] = relationship(
        back_populates="photos",
    )
