from typing import Protocol

from geodom_backend.geo.data import GeocodedAddress

class GeocodingProvider(Protocol):
    async def geocode(self, address: str) -> GeocodedAddress:
        ...
