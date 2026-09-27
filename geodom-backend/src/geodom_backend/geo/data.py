from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True, slots=True)
class GeocodedAddress:
    address: str

    latitude: Decimal
    longitude: Decimal

    district_name: str
    house_number: str | None

    method: str
