from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from fastapi import Depends

from geodom_backend.config import settings
from geodom_backend.db import DatabaseSession
from geodom_backend.db.repositories import DistrictRepository
from geodom_backend.geo.nominatim import NominatimGeocodingProvider
from geodom_backend.geo.service import GeoService

async def get_geo_service(session: DatabaseSession) -> AsyncIterator[GeoService]:
    async with httpx.AsyncClient(
        timeout=settings.geocoding_timeout_seconds,
        headers={
            "User-Agent": settings.geocoding_user_agent
        }
    ) as client:
        provider = NominatimGeocodingProvider(
            client=client,
            base_url=settings.geocoding_base_url,
            city=settings.geocoding_city
        )

        yield GeoService(
            provider=provider,
            district_repository=DistrictRepository(session)
        )

GeoServiceDep = Annotated[
    GeoService,
    Depends(get_geo_service)
]
