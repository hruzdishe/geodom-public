from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from geodom_backend.apartments.enums import (
    ApartmentDealType,
    ApartmentOrigin,
    ApartmentStatus,
    RentPeriod
)

@dataclass(frozen=True, slots=True)
class ApartmentSeedData:
    dataset_id: str
    external_id: str

    title: str

    price: Decimal
    currency: str

    deal_type: ApartmentDealType
    rent_period: RentPeriod | None

    area: Decimal
    rooms: int
    floor: int
    total_floors: int

    building_year: int | None

    address: str

    latitude: Decimal
    longitude: Decimal

    coordinate_method: str
    district_assignment_method: str

    district_source_id: str
    district_name: str

    complex_source_id: str | None
    complex_name: str | None
    complex_source_url: str | None

    market_type: str
    offer_type: str

    origin: ApartmentOrigin

    source: str
    source_id: str
    source_url: str

    source_updated_at: datetime | None
    collected_at: datetime

    raw_sha256: str
    is_demo: bool

    status: ApartmentStatus
