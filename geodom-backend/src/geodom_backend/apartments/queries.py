from dataclasses import dataclass
from decimal import Decimal

from geodom_backend.apartments.enums import ApartmentDealType, RentPeriod

@dataclass(frozen=True, slots=True)
class ApartmentQuery:
    deal_type: ApartmentDealType | None = None
    rent_period: RentPeriod | None = None

    price_min: Decimal | None = None
    price_max: Decimal | None = None

    rooms: int | None = None
    district_id: int | None = None
