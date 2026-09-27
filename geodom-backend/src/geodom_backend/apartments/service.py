from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from geodom_backend.apartments.enums import ApartmentDealType, ApartmentStatus
from geodom_backend.apartments.exceptions import (
    ApartmentNotFoundError,
    ApartmentPermissionError,
    InvalidApartmentDataError,
)
from geodom_backend.apartments.queries import ApartmentQuery
from geodom_backend.apartments.schemas import (
    ApartmentCreateRequest,
    ApartmentUpdateRequest,
)
from geodom_backend.db.models import Apartment, User
from geodom_backend.db.repositories import (
    ApartmentFeaturesRepository,
    ApartmentRepository,
)
from geodom_backend.geo.service import GeoService


@dataclass(frozen=True, slots=True)
class ApartmentPage:
    items: list[Apartment]

    total: int
    limit: int
    offset: int

class ApartmentService:
    def __init__(self, *, session: AsyncSession, repository: ApartmentRepository, features_repository: ApartmentFeaturesRepository, geo_service: GeoService):
        self._session = session
        self._repository = repository
        self._features = features_repository
        self._geo = geo_service

    async def get_catalog(self, *, query: ApartmentQuery, limit: int, offset: int) -> ApartmentPage:
        items = await self._repository.get_published(
            query=query,
            limit=limit,
            offset=offset,
        )

        total = await self._repository.count_published(query=query)

        return ApartmentPage(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_by_id(self, apartment_id: int) -> Apartment:
        apartment = await self._repository.get_by_id(apartment_id)
        if apartment is None or apartment.status == ApartmentStatus.DELETED:
            raise ApartmentNotFoundError

        return apartment

    async def get_public_by_id(self, apartment_id: int ) -> Apartment:
        apartment = await self._repository.get_by_id(apartment_id)
        if apartment is None or apartment.status != ApartmentStatus.PUBLISHED:
            raise ApartmentNotFoundError

        return apartment

    async def get_my_apartments(self, user: User) -> list[Apartment]:
        return await self._repository.get_by_owner(user.id)

    async def get_my_apartment(self, *, apartment_id: int, user: User) -> Apartment:
        return await self._get_owned(apartment_id=apartment_id, user=user)

    async def create(
        self,
        *,
        user: User,
        data: ApartmentCreateRequest,
    ) -> Apartment:
        try:
            geocoded, district = await self._geo.resolve_address(
                data.address
            )

            apartment = await self._repository.create_user_apartment(
                owner_id=user.id,
                district_id=district.id,
                title=data.title,
                price=data.price,
                deal_type=data.deal_type,
                rent_period=data.rent_period,
                rooms=data.rooms,
                area=data.area,
                floor=data.floor,
                total_floors=data.total_floors,
                address=geocoded.address,
                house_number=geocoded.house_number,
                latitude=geocoded.latitude,
                longitude=geocoded.longitude,
                description=data.description,
                building_year=data.building_year,
                coordinate_method=geocoded.method,
            )

            self._validate_apartment(apartment)

            await self._features.create_pending(
                apartment.id
            )

            await self._session.commit()

        except Exception:
            await self._session.rollback()
            raise

        return await self.get_by_id(apartment.id)

    async def update(
        self,
        *,
        apartment_id: int,
        user: User,
        data: ApartmentUpdateRequest,
    ) -> Apartment:
        apartment = await self._get_owned(
            apartment_id=apartment_id,
            user=user,
        )

        try:
            changes = data.model_dump(
                exclude_unset=True
            )

            if changes.get("address") == apartment.address:
                changes.pop("address")

            if "address" in changes:
                address = changes.pop("address")

                geocoded, district = (
                    await self._geo.resolve_address(
                        address
                    )
                )

                apartment.address = geocoded.address
                apartment.house_number = (
                    geocoded.house_number
                )
                apartment.latitude = (
                    geocoded.latitude
                )
                apartment.longitude = (
                    geocoded.longitude
                )
                apartment.coordinate_method = (
                    geocoded.method
                )

                apartment.district_id = district.id
                apartment.district_assignment_method = (
                    "geocoder"
                )

                await self._features.reset_pending(
                    apartment.id
                )

            for field, value in changes.items():
                setattr(
                    apartment,
                    field,
                    value,
                )

            self._validate_apartment(
                apartment
            )

            await self._repository.flush()
            await self._session.commit()

        except Exception:
            await self._session.rollback()
            raise

        return await self.get_by_id(
            apartment.id
        )

    async def hide(self, *, apartment_id: int, user: User) -> Apartment:
        apartment = await self._get_owned(apartment_id=apartment_id, user=user)
        apartment.status = ApartmentStatus.HIDDEN

        await self._commit()

        return apartment

    async def publish(self, *, apartment_id: int, user: User) -> Apartment:
        apartment = await self._get_owned(apartment_id=apartment_id, user=user)
        apartment.status = ApartmentStatus.PUBLISHED

        await self._commit()

        return apartment

    async def delete(self, *, apartment_id: int, user: User):
        apartment = await self._get_owned(apartment_id=apartment_id, user=user)
        apartment.status = ApartmentStatus.DELETED

        await self._commit()

    async def _get_owned(self, *, apartment_id: int, user: User) -> Apartment:
        apartment = await self._repository.get_by_id(apartment_id)
        if apartment is None or apartment.status == ApartmentStatus.DELETED:
            raise ApartmentNotFoundError

        if apartment.owner_id != user.id:
            raise ApartmentPermissionError

        return apartment

    @staticmethod
    def _validate_apartment(apartment: Apartment):
        if apartment.floor > apartment.total_floors:
            raise InvalidApartmentDataError(
                "floor cannot be greater than total_floors"
            )

        if apartment.deal_type == ApartmentDealType.SALE and apartment.rent_period is not None:
            raise InvalidApartmentDataError(
                "rent_period must be empty for sale listings"
            )

        if apartment.deal_type == ApartmentDealType.RENT and apartment.rent_period is None:
            raise InvalidApartmentDataError(
                "rent_period is required for rental listings"
            )

    async def _commit(self):
        try:
            await self._repository.flush()
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
