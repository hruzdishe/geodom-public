from typing import Annotated

from fastapi import Depends

from geodom_backend.db import DatabaseSession
from geodom_backend.db.repositories import DistrictRepository
from geodom_backend.districts.service import DistrictService


def get_district_repository(session: DatabaseSession) -> DistrictRepository:
    return DistrictRepository(session)

DistrictRepositoryDep = Annotated[
    DistrictRepository,
    Depends(get_district_repository)
]

def get_district_service(repository: DistrictRepositoryDep) -> DistrictService:
    return DistrictService(
        repository=repository
    )

DistrictServiceDep = Annotated[
    DistrictService,
    Depends(get_district_service)
]
