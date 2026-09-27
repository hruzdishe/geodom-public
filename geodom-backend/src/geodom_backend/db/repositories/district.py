from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from geodom_backend.db.models import District


class DistrictRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(
        self,
        district_id: int,
    ) -> District | None:
        return await self._session.get(
            District,
            district_id,
        )

    async def get_by_name(
        self,
        name: str,
    ) -> District | None:
        statement = select(District).where(
            District.name == name
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
    ) -> District | None:
        statement = select(District).where(
            District.source == source,
            District.source_id == source_id,
        )

        result = await self._session.execute(
            statement
        )

        return result.scalar_one_or_none()

    async def get_all(
        self,
    ) -> list[District]:
        statement = select(District).order_by(
            District.name
        )

        result = await self._session.execute(
            statement
        )

        return list(result.scalars().all())

    async def get_or_create_seed(
        self,
        *,
        source: str,
        source_id: str,
        name: str,
    ) -> District:
        district = await self.get_by_source(
            source=source,
            source_id=source_id,
        )

        if district is not None:
            if district.name != name:
                district.name = name

            return district

        district = await self.get_by_name(name)

        if district is not None:
            if district.source not in {
                None,
                source,
            }:
                raise ValueError(
                    f"District {name!r} already belongs "
                    f"to source {district.source!r}"
                )

            if district.source_id not in {
                None,
                source_id,
            }:
                raise ValueError(
                    f"District {name!r} already has "
                    f"source_id {district.source_id!r}"
                )

            district.source = source
            district.source_id = source_id

            return district

        district = District(
            name=name,
            source=source,
            source_id=source_id,
        )

        self._session.add(district)

        await self._session.flush()

        return district
