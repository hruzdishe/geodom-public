from typing import Any, Protocol

from geodom_backend.db.models import Apartment

class ScoringProvider(Protocol):
    model_version: str
    scoring_version: str

    async def recommend(self, *, apartments: list[Apartment], preferences: dict[str, Any], limit: int) -> dict[str, Any]:
        ...
