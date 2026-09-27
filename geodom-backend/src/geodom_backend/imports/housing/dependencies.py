from sqlalchemy.ext.asyncio import AsyncSession

from geodom_backend.db.repositories import (
    ApartmentRepository, DistrictRepository
)
from geodom_backend.imports.housing.service import HousingImportService
from geodom_backend.imports.housing.validator import HousingSnapshotValidator

def create_housing_import_service(session: AsyncSession) -> HousingImportService:
    return HousingImportService(
        session=session,
        district_repository=DistrictRepository(session),
        apartment_repository=ApartmentRepository(session),
        validator=HousingSnapshotValidator()
    )
