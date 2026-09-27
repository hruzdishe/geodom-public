from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from geodom_backend.apartments.enums import ApartmentFeatureStatus
from geodom_backend.apartments.feature_data import CalculatedApartmentFeatures
from geodom_backend.db.models import ApartmentFeatures


class ApartmentFeaturesRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_apartment_id(self, apartment_id: int) -> ApartmentFeatures | None:
        statement = select(
            ApartmentFeatures
        ).where(ApartmentFeatures.apartment_id == apartment_id)

        result = await self._session.execute(statement)

        return result.scalar_one_or_none()

    async def create_pending(self, apartment_id: int) -> ApartmentFeatures:
        statement = (
            insert(ApartmentFeatures)
            .values(
                apartment_id=apartment_id,
                status=ApartmentFeatureStatus.PENDING
            )
            .on_conflict_do_nothing(
                index_elements=[
                    ApartmentFeatures.apartment_id
                ]
            )
            .returning(ApartmentFeatures)
        )

        result = await self._session.execute(statement)

        features = result.scalar_one_or_none()
        if features is not None: return features

        existing = await self.get_by_apartment_id(apartment_id)
        if existing is None: raise RuntimeError("Failed to create apartment features")

        return existing

    async def save_calculated(self, *, apartment_id: int, data: CalculatedApartmentFeatures) -> ApartmentFeatures:
        values = {
            "apartment_id": apartment_id,
            "status": (
                ApartmentFeatureStatus.READY
            ),
            "schools_1km": data.schools_1km,
            "kindergartens_1km": (
                data.kindergartens_1km
            ),
            "parks_1km": data.parks_1km,
            "shops_1km": data.shops_1km,
            "transport_stops_1km": (
                data.transport_stops_1km
            ),
            "nearest_school_m": (
                data.nearest_school_m
            ),
            "nearest_kindergarten_m": (
                data.nearest_kindergarten_m
            ),
            "nearest_park_m": (
                data.nearest_park_m
            ),
            "nearest_transport_m": (
                data.nearest_transport_m
            ),
            "feature_version": (
                data.feature_version
            ),
            "error": None,
            "computed_at": data.computed_at or datetime.now(UTC),
        }

        statement = (
            insert(ApartmentFeatures)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[
                    ApartmentFeatures.apartment_id
                ],
                set_={
                    key: value
                    for key, value in values.items() if key != "apartment_id"
                }
            )
            .returning(ApartmentFeatures)
        )

        result = await self._session.execute(statement)

        return result.scalar_one()

    async def make_failed(self, *, apartment_id: int, error: str) -> ApartmentFeatures:
        statement = (
            insert(ApartmentFeatures)
            .values(
                apartment_id=apartment_id,
                status=ApartmentFeatureStatus.FAILED,
                error=error
            )
            .on_conflict_do_update(
                index_elements=[
                    ApartmentFeatures.apartment_id
                ],
                set_={
                    "status": ApartmentFeatureStatus.FAILED,
                    "error": error
                }
            )
            .returning(ApartmentFeatures)
        )

        result = await self._session.execute(statement)

        return result.scalar_one()

    async def reset_pending(self, apartment_id: int) -> ApartmentFeatures:
        values = {
            "apartment_id": apartment_id,
            "status": ApartmentFeatureStatus.PENDING,
            "schools_1km": None,
            "kindergartens_1km": None,
            "parks_1km": None,
            "shops_1km": None,
            "transport_stops_1km": None,
            "nearest_school_m": None,
            "nearest_kindergarten_m": None,
            "nearest_park_m": None,
            "nearest_transport_m": None,
            "feature_version": None,
            "error": None,
            "computed_at": None,
        }

        statement = (
            insert(ApartmentFeatures)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[ApartmentFeatures.apartment_id],
                set_={
                    key: value
                    for key, value in values.items() if key != "apartment_id"
                }
            )
            .returning(ApartmentFeatures)
        )

        result = await self._session.execute(statement)

        return result.scalar_one()
