from typing import Annotated

from fastapi import Depends

from geodom_backend.apartments.service import ApartmentService
from geodom_backend.db import DatabaseSession
from geodom_backend.db.repositories import ApartmentFeaturesRepository, ApartmentRepository
from geodom_backend.geo.dependencies import GeoServiceDep


def get_apartment_repository(session: DatabaseSession) -> ApartmentRepository:
    return ApartmentRepository(session)

ApartmentRepositoryDep = Annotated[
    ApartmentRepository,
    Depends(get_apartment_repository)
]

def get_apartment_features_repository(session: DatabaseSession) -> ApartmentFeaturesRepository:
    return ApartmentFeaturesRepository(session)

ApartmentFeaturesRepositoryDep = Annotated[
    ApartmentFeaturesRepository,
    Depends(
        get_apartment_features_repository
    )
]

def get_apartment_service(
    session: DatabaseSession,
    repository: ApartmentRepositoryDep,
    features_repository: ApartmentFeaturesRepositoryDep,
    geo_service: GeoServiceDep
) -> ApartmentService:
    return ApartmentService(
        session=session,
        repository=repository,
        features_repository=features_repository,
        geo_service=geo_service,
    )

ApartmentServiceDep = Annotated[
    ApartmentService,
    Depends(get_apartment_service)
]
