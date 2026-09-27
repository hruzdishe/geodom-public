from decimal import Decimal

import httpx
from pydantic import BaseModel, ConfigDict

from geodom_backend.geo.data import GeocodedAddress
from geodom_backend.geo.exceptions import (
    AddressNotFoundError,
    AddressOutsideCityError,
    DistrictNotResolvedError,
    GeocodingUnavailableError
)

class NominatimAddress(BaseModel):
    house_number: str | None = None

    city: str | None = None
    town: str | None = None
    municipality: str | None = None

    city_district: str | None = None
    district: str | None = None
    suburb: str | None = None

    model_config = ConfigDict(extra="ignore")

class NominatimResult(BaseModel):
    lat: Decimal
    lon: Decimal

    display_name: str
    address: NominatimAddress

    model_config = ConfigDict(extra="ignore")

class NominatimGeocodingProvider:
    def __init__(self, *, client: httpx.AsyncClient, base_url: str, city: str):
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._city = city

    async def geocode(self, address: str) -> GeocodedAddress:
        query = self._build_query(address)

        try:
            response = await self._client.get(
                f"{self._base_url}/search",
                params={
                    "q": query,
                    "format": "jsonv2",
                    "addressdetails": 1,
                    "limit": 1,
                    "countrycodes": "ru"
                },
                headers={
                    "Accept-Language": "ru"
                }
            )

            response.raise_for_status()

        except httpx.HTTPError as e:
            raise GeocodingUnavailableError from e

        payload = response.json()
        if not payload:
            raise AddressNotFoundError

        result = NominatimResult.model_validate(payload[0])
        self._validate_city(result)

        district_name = self._resolve_district(result)

        return GeocodedAddress(
            address=result.display_name,
            latitude=result.lat,
            longitude=result.lon,
            district_name=district_name,
            house_number=result.address.house_number,
            method="nominatim"
        )

    def _build_query(self, address: str) -> str:
        cleaned = address.strip()

        if self._city.lower() in cleaned.lower(): return cleaned

        return f"{self._city}, {cleaned}"

    def _validate_city(self, result: NominatimResult):
        candidates = {
            value.lower()
            for value in (
                result.address.city,
                result.address.town,
                result.address.municipality,
            )
            if value
        }

        expected = self._city.lower()
        if candidates and not any(expected in candidate for candidate in candidates):
            raise AddressOutsideCityError

    @staticmethod
    def _resolve_district(result: NominatimResult) -> str:
        for value in (
            result.address.city_district,
            result.address.district,
            result.address.suburb,
        ):
            if value: return value

        raise DistrictNotResolvedError
