from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Uuid,
    func
)
from sqlalchemy.orm import Mapped, mapped_column

from geodom_backend.db.base import Base

class RecommendationLog(Base):
    __tablename__ = "recommendation_logs"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    request_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        index=True
    )

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL"
        ),
        nullable=True,
        index=True
    )

    apartment_id: Mapped[int] = mapped_column(
        ForeignKey(
            "apartments.id",
            ondelete="RESTRICT"
        ),
        nullable=False,
        index=True
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    score: Mapped[Decimal | None] = mapped_column(
        Numeric(
            precision=8,
            scale=4
        ),
        nullable=True
    )

    model_version: Mapped[str] = mapped_column(
        String(128),
        nullable=False
    )

    scoring_version: Mapped[str] = mapped_column(
        String(128),
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
