import re

from geodom_backend.db.models import District
from geodom_backend.db.repositories import DistrictRepository
from geodom_backend.geo.data import GeocodedAddress
from geodom_backend.geo.exceptions import DistrictNotResolvedError
from geodom_backend.geo.provider import GeocodingProvider


class GeoService:
    def __init__(self, *, provider: GeocodingProvider, district_repository: DistrictRepository):
        self._provider = provider
        self._districts = district_repository

    async def resolve_address(self, address: str) -> tuple[GeocodedAddress, District]:
        geocoded = await self._provider.geocode(address)
        districts = await self._districts.get_all()

        normalized_result = self._normalize_district_name(geocoded.district_name)

        for district in districts:
            normalized_district = self._normalize_district_name(district.name)
            if normalized_district == normalized_result:
                return geocoded, district

        raise DistrictNotResolvedError(geocoded.district_name)

    @staticmethod
    def _normalize_district_name(value: str) -> str:
        value = value.lower()
        value = value.replace("район", "")
        value = re.sub(
            r"[^а-яёa-z0-9]+",
            " ",
            value
        )

        return value.strip()
