from decimal import Decimal
from uuid import uuid4

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from geodom_backend.apartments.data import ApartmentSeedData
from geodom_backend.apartments.enums import (
    ApartmentDealType,
    ApartmentOrigin,
    ApartmentStatus,
    RentPeriod,
)
from geodom_backend.apartments.queries import ApartmentQuery
from geodom_backend.db.models import Apartment


class ApartmentRepository:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def get_by_id(
        self,
        apartment_id: int,
    ) -> Apartment | None:
        statement = (
            select(Apartment)
            .options(
                selectinload(Apartment.district),
                selectinload(Apartment.photos),
                selectinload(Apartment.features)
            )
            .where(
                Apartment.id == apartment_id,
            )
        )

        result = await self._session.execute(
            statement
        )

        return result.scalar_one_or_none()

    async def get_by_source(
        self,
        *,
        source: str,
        source_id: str,
    ) -> Apartment | None:
        statement = select(Apartment).where(
            Apartment.source == source,
            Apartment.source_id == source_id,
        )

        result = await self._session.execute(
            statement
        )

        return result.scalar_one_or_none()

    async def get_by_dataset_id(
        self,
        dataset_id: str,
    ) -> Apartment | None:
        statement = select(Apartment).where(
            Apartment.dataset_id == dataset_id
        )

        result = await self._session.execute(
            statement
        )

        return result.scalar_one_or_none()

    async def get_published(
        self,
        *,
        query: ApartmentQuery,
        limit: int,
        offset: int,
    ) -> list[Apartment]:
        conditions = self._build_conditions(
            query
        )

        statement = (
            select(Apartment)
            .options(
                selectinload(Apartment.district),
                selectinload(Apartment.photos),
            )
            .where(
                Apartment.status
                == ApartmentStatus.PUBLISHED,
                *conditions,
            )
            .order_by(
                Apartment.created_at.desc(),
                Apartment.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        result = await self._session.execute(
            statement
        )

        return list(
            result.scalars().all()
        )

    async def count_published(
        self,
        *,
        query: ApartmentQuery,
    ) -> int:
        conditions = self._build_conditions(
            query
        )

        statement = (
            select(func.count(Apartment.id))
            .where(
                Apartment.status
                == ApartmentStatus.PUBLISHED,
                *conditions,
            )
        )

        result = await self._session.execute(
            statement
        )

        return result.scalar_one()

    async def get_by_owner(
        self,
        owner_id: int,
    ) -> list[Apartment]:
        statement = (
            select(Apartment)
            .options(
                selectinload(Apartment.district),
                selectinload(Apartment.photos),
            )
            .where(
                Apartment.owner_id == owner_id,
                Apartment.status
                != ApartmentStatus.DELETED,
            )
            .order_by(
                Apartment.created_at.desc()
            )
        )

        result = await self._session.execute(
            statement
        )

        return list(
            result.scalars().all()
        )

    async def create_user_apartment(
        self,
        *,
        owner_id: int,
        district_id: int,
        title: str,
        price: Decimal,
        deal_type: ApartmentDealType,
        rent_period: RentPeriod | None,
        rooms: int,
        area: Decimal,
        floor: int,
        total_floors: int,
        address: str,
        house_number: str | None,
        latitude: Decimal,
        longitude: Decimal,
        description: str | None,
        building_year: int | None,
        coordinate_method: str
    ) -> Apartment:
        apartment = Apartment(
            owner_id=owner_id,
            district_id=district_id,
            title=title,
            price=price,
            currency="RUB",
            deal_type=deal_type,
            rent_period=rent_period,
            rooms=rooms,
            area=area,
            floor=floor,
            total_floors=total_floors,
            address=address,
            house_number=house_number,
            latitude=latitude,
            longitude=longitude,
            description=description,
            building_year=building_year,
            origin=ApartmentOrigin.USER,
            source="user",
            source_id=uuid4().hex,
            status=ApartmentStatus.PUBLISHED,
            coordinate_method=coordinate_method,
            district_assignment_method="geocoder"
        )

        self._session.add(apartment)

        await self._session.flush()

        return apartment

    async def upsert_seed(
        self,
        *,
        data: ApartmentSeedData,
        district_id: int,
    ) -> Apartment:
        values = {
            "dataset_id": data.dataset_id,
            "external_id": data.external_id,
            "owner_id": None,
            "district_id": district_id,
            "title": data.title,
            "price": data.price,
            "currency": data.currency,
            "deal_type": data.deal_type,
            "rent_period": data.rent_period,
            "rooms": data.rooms,
            "area": data.area,
            "floor": data.floor,
            "total_floors": data.total_floors,
            "building_year": data.building_year,
            "address": data.address,
            "latitude": data.latitude,
            "longitude": data.longitude,
            "coordinate_method": (
                data.coordinate_method
            ),
            "district_assignment_method": (
                data.district_assignment_method
            ),
            "complex_source_id": (
                data.complex_source_id
            ),
            "complex_name": (
                data.complex_name
            ),
            "complex_source_url": (
                data.complex_source_url
            ),
            "market_type": data.market_type,
            "offer_type": data.offer_type,
            "origin": data.origin,
            "source": data.source,
            "source_id": data.source_id,
            "source_url": data.source_url,
            "source_updated_at": (
                data.source_updated_at
            ),
            "collected_at": data.collected_at,
            "raw_sha256": data.raw_sha256,
            "is_demo": data.is_demo,
            "status": data.status,
        }

        statement = (
            insert(Apartment)
            .values(**values)
            .on_conflict_do_update(
                constraint=(
                    "uq_apartments_source_source_id"
                ),
                set_={
                    key: value
                    for key, value in values.items()
                    if key not in {
                        "source",
                        "source_id",
                    }
                },
            )
            .returning(Apartment)
        )

        result = await self._session.execute(
            statement
        )

        return result.scalar_one()

    async def get_scoring_candidates(self, *, limit: int = 1000) -> list[Apartment]:
        statement = (
            select(Apartment)
            .options(
                selectinload(Apartment.district),
                selectinload(Apartment.photos),
                selectinload(Apartment.features),
            )
            .where(Apartment.status == ApartmentStatus.PUBLISHED)
            .order_by(Apartment.id)
            .limit(limit)
        )

        result = await self._session.execute(statement)

        return list(result.scalars().all())

    async def get_ids_by_dataset_ids(self, dataset_ids: set[str]) -> dict[str, int]:
        if not dataset_ids: return {}

        statement = (
            select(
                Apartment.dataset_id,
                Apartment.id
            )
            .where(
                Apartment.dataset_id.in_(dataset_ids)
            )
        )

        result = await self._session.execute(statement)

        return {
            dataset_id: apartment_id
            for dataset_id, apartment_id
            in result.all() if dataset_id is not None
        }

    async def flush(self):
        await self._session.flush()

    @staticmethod
    def _build_conditions(
        query: ApartmentQuery,
    ) -> list[ColumnElement[bool]]:
        conditions: list[
            ColumnElement[bool]
        ] = []

        if query.deal_type is not None:
            conditions.append(
                Apartment.deal_type
                == query.deal_type
            )

        if query.rent_period is not None:
            conditions.append(
                Apartment.rent_period
                == query.rent_period
            )

        if query.price_min is not None:
            conditions.append(
                Apartment.price
                >= query.price_min
            )

        if query.price_max is not None:
            conditions.append(
                Apartment.price
                <= query.price_max
            )

        if query.rooms is not None:
            conditions.append(
                Apartment.rooms
                == query.rooms
            )

        if query.district_id is not None:
            conditions.append(
                Apartment.district_id
                == query.district_id
            )

        return conditions
