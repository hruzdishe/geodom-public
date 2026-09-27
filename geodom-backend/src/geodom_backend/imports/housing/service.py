from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from geodom_backend.db.repositories import ApartmentRepository, DistrictRepository
from geodom_backend.imports.housing.mapper import map_apartment_record
from geodom_backend.imports.housing.reader import HousingSnapshot
from geodom_backend.imports.housing.validator import HousingSnapshotValidator

@dataclass(frozen=True, slots=True)
class HousingImportReport:
    dataset_version: str

    districts_processed: int
    apartments_processed: int

    media_validated: int
    media_imported: int

class HousingImportService:
    def __init__(self, session: AsyncSession, district_repository: DistrictRepository, apartment_repository: ApartmentRepository, validator: HousingSnapshotValidator):
        self._session = session
        self._districts = district_repository
        self._apartments = apartment_repository
        self._validator = validator

    async def import_snapshot(
        self, snapshot: HousingSnapshot, *, validate_files: bool = False
    ) -> HousingImportReport:
        validation_report = self._validator.validate(snapshot, validate_files=validate_files)

        district_cache: dict[tuple[str, str], int] = {}
        try:
            for record in snapshot.apartments:
                apartment = map_apartment_record(record)
                district_key = (apartment.source, apartment.district_source_id)
                district_id = district_cache.get(district_key)
                if district_id is None:
                    district = (
                        await self._districts
                        .get_or_create_seed(
                            source=apartment.source,
                            source_id=apartment.district_source_id,
                            name=apartment.district_name
                        )
                    )

                    district_id = district.id
                    district_cache[district_key] = district_id

                await self._apartments.upsert_seed(data=apartment, district_id=district_id)

            await self._session.commit()

        except Exception:
            await self._session.rollback()
            raise

        return HousingImportReport(
            dataset_version=snapshot.manifest.dataset_version,
            districts_processed=validation_report.districts,
            apartments_processed=validation_report.apartments,
            media_validated=validation_report.media,
            media_imported=0
        )
