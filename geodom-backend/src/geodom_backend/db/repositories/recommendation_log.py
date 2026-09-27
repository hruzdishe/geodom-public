from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from geodom_backend.db.models import RecommendationLog


class RecommendationLogRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_many(self, *, request_id: UUID, user_id: int | None, rows: list[dict], model_version: str, scoring_version: str):
        logs = [
            RecommendationLog(
                request_id=request_id,
                user_id=user_id,
                apartment_id=row["apartment_id"],
                position=row["position"],
                score=(
                    Decimal(str(row["score"]))
                    if row["score"] is not None
                    else None
                ),
                model_version=model_version,
                scoring_version=scoring_version
            )
            for row in rows
        ]

        self._session.add_all(logs)

        await self._session.flush()
