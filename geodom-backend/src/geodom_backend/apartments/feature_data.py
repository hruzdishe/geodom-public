from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CalculatedApartmentFeatures:
    schools_1km: int
    kindergartens_1km: int
    parks_1km: int
    shops_1km: int
    transport_stops_1km: int

    nearest_school_m: Decimal | None
    nearest_kindergarten_m: Decimal | None
    nearest_park_m: Decimal | None
    nearest_transport_m: Decimal | None

    feature_version: str

    computed_at: datetime | None = None
