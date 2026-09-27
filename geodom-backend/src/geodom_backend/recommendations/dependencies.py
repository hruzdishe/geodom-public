from typing import Annotated

from fastapi import Depends

from geodom_backend.apartments.dependencies import ApartmentRepositoryDep
from geodom_backend.apartments.presenter_dependencies import ApartmentPresenterDep
from geodom_backend.db import DatabaseSession
from geodom_backend.db.repositories import RecommendationLogRepository
from geodom_backend.scoring import ApartmentScoringAdapter

from .service import RecommendationService

def get_recommendation_log_repository(session: DatabaseSession) -> RecommendationLogRepository:
    return RecommendationLogRepository(session)

RecommendationLogRepositoryDep = Annotated[
    RecommendationLogRepository,
    Depends(get_recommendation_log_repository)
]

def get_scoring_adapter() -> ApartmentScoringAdapter:
    return ApartmentScoringAdapter()

ScoringAdapterDep = Annotated[
    ApartmentScoringAdapter,
    Depends(get_scoring_adapter)
]

def get_recommendation_service(
    session: DatabaseSession,
    apartment_repository: ApartmentRepositoryDep,
    log_repository: RecommendationLogRepositoryDep,
    scoring: ScoringAdapterDep,
    presenter: ApartmentPresenterDep,
) -> RecommendationService:
    return RecommendationService(
        session=session,
        apartment_repository=apartment_repository,
        log_repository=log_repository,
        scoring=scoring,
        presenter=presenter,
    )

RecommendationServiceDep = Annotated[
    RecommendationService,
    Depends(get_recommendation_service)
]
