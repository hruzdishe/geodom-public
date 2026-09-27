import logging

from krasnoyarsk_ml.scoring import ScoringConfig, WorkLocation, commute
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from geodom_backend.apartments.schemas import ApartmentResponse
from geodom_backend.apartments.presenter import ApartmentPresenter
from geodom_backend.db.models import Apartment, User
from geodom_backend.db.repositories import (
    ApartmentRepository,
    RecommendationLogRepository,
)
from geodom_backend.scoring.provider import ScoringProvider

from .schemas import (
    RecommendationComponentResponse,
    RecommendationItemResponse,
    RecommendationRequest,
    RecommendationResponse,
)

logger = logging.getLogger(__name__)

FALLBACK_MODEL_VERSION = "fallback_catalog_v1"
FALLBACK_SCORING_VERSION = "fallback_v1"

class RecommendationService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        apartment_repository: ApartmentRepository,
        log_repository: RecommendationLogRepository,
        scoring: ScoringProvider,
        presenter: ApartmentPresenter,
    ):
        self._session = session
        self._apartments = apartment_repository
        self._logs = log_repository
        self._scoring = scoring
        self._presenter = presenter

    async def recommend(self, *, data: RecommendationRequest, user: User | None) -> RecommendationResponse:
        request_id = uuid4()

        apartments = (
            await self._apartments
            .get_scoring_candidates(limit=1000)
        )

        try:
            raw = await self._scoring.recommend(
                apartments=apartments,
                preferences=data.scoring_preferences(),
                limit=data.limit
            )

            response = self._build_response(
                request_id=request_id,
                apartments=apartments,
                raw=raw
            )
        except Exception:
            logger.exception("Scoring failed for request %s", request_id)

            response = self._build_fallback(
                request_id=request_id,
                apartments=apartments,
                data=data
            )

        apartments_by_id = {apartment.id: apartment for apartment in apartments}
        for item in response.items:
            item.apartment = await self._presenter.response(
                apartments_by_id[item.apartment.id], public_only=True
            )

        try:
            await self._logs.create_many(
                request_id=request_id,
                user_id=user.id if user is not None else None,
                rows=[
                    {
                        "apartment_id": item.apartment.id,
                        "position": item.rank,
                        "score": item.score
                    }
                    for item in response.items
                ],
                model_version=response.model_version,
                scoring_version=response.scoring_version
            )

            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        return response

    def _build_response(self, *, request_id, apartments: list[Apartment], raw: dict) -> RecommendationResponse:
        apartments_by_id = {
            str(apartment.id): apartment
            for apartment in apartments
        }

        items: list[RecommendationItemResponse] = []

        for result in raw["results"]:
            apartment_id = str(result["apartment_id"])
            apartment = apartments_by_id.get(apartment_id)
            if apartment is None:
                raise RuntimeError(
                    f"Scoring returned unknown apartment {apartment_id}"
                )

            items.append(
                RecommendationItemResponse(
                    rank=result["rank"],
                    apartment=self._apartment_response(apartment),
                    score=result["score"],
                    score_upper_bound=result["score_upper_bound"],
                    score_coverage=result["score_coverage"],
                    scoring_status=result["scoring_status"],
                    components=[
                        RecommendationComponentResponse(**component)
                        for component in result["components"]
                    ],
                    commute=result["commute"]
                )
            )

        return RecommendationResponse(
            request_id=request_id,
            model_version=self._scoring.model_version,
            scoring_version=raw.get("scoring_version", self._scoring.scoring_version),
            fallback_used=False,
            status=raw["status"],
            eligible_count=raw["eligible_count"],
            returned_count=len(items),
            filter_rejection_counts=raw["filter_rejection_counts"],
            unsupported_priorities=raw["unsupported_priorities"],
            limitations=raw["limitations"],
            items=items
        )

    def _build_fallback(self, *, request_id, apartments: list[Apartment], data: RecommendationRequest) -> RecommendationResponse:
        filtered = [
            apartment
            for apartment in apartments
            if self._matches_hard_filters(apartment=apartment, data=data)
        ]

        selected = filtered[:data.limit]

        items = [
            RecommendationItemResponse(
                rank=position,
                apartment=self._apartment_response(apartment),
                score=None,
                score_upper_bound=None,
                score_coverage=0.0,
                scoring_status="unavailable",
                components=[],
                commute=None
            )
            for position, apartment in enumerate(selected, start=1)
        ]

        return RecommendationResponse(
            request_id=request_id,
            model_version=FALLBACK_MODEL_VERSION,
            scoring_version=FALLBACK_SCORING_VERSION,
            fallback_used=True,
            status="fallback" if items else "no_matches",
            eligible_count=len(filtered),
            returned_count=len(items),
            filter_rejection_counts={},
            unsupported_priorities=[],
            limitations=[
                (
                    "Scoring service was unavailable. "
                    "Results were filtered only by "
                    "basic apartment parameters"
                )
            ],
            items=items
        )

    @staticmethod
    def _matches_hard_filters(*, apartment: Apartment, data: RecommendationRequest) -> bool:
        if apartment.deal_type != data.offer_type: return False
        if data.price_min is not None and apartment.price < data.price_min: return False
        if data.price_max is not None and apartment.price > data.price_max: return False
        if data.rooms and apartment.rooms not in data.rooms: return False
        if data.districts and apartment.district.name not in data.districts: return False

        if data.work and data.work.max_minutes is not None:
            trip=commute({'lat':float(apartment.latitude), 'lon':float(apartment.longitude)},
                WorkLocation(**data.work.model_dump()), ScoringConfig(assumed_car_speed_kmh=30))
            if trip['estimated_minutes'] is None or trip['exceeds_desired_time']: return False
        return True

    @staticmethod
    def _apartment_response(apartment: Apartment):
        return ApartmentResponse.model_validate(apartment)
