from geodom_backend.db.models import District
from geodom_backend.db.repositories import DistrictRepository
from geodom_backend.districts.exceptions import DistrictNotFoundError


class DistrictService:
    def __init__(self, repository: DistrictRepository):
        self._repository = repository

    async def get_by_id(self, district_id: int) -> District:
        district = await self._repository.get_by_id(district_id)
        if district is None: raise DistrictNotFoundError
        return district

    async def get_all(self) -> list[District]:
        return await self._repository.get_all()
