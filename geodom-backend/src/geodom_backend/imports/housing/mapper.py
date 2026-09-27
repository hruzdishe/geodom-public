from geodom_backend.apartments.data import ApartmentSeedData
from geodom_backend.apartments.enums import (
    ApartmentDealType,
    ApartmentOrigin,
    ApartmentStatus,
    RentPeriod,
)
from geodom_backend.imports.housing.schemas import HousingApartmentRecord


class UnsupportedOfferTypeError(ValueError):
    pass

def map_offer_type(offer_type: str) -> tuple[ApartmentDealType, RentPeriod | None]:
    normalized = offer_type.strip().lower()

    if normalized == "sale":
        return (ApartmentDealType.SALE, None)

    if normalized in {"rent", "rent_month", "long_rent"}:
        return (ApartmentDealType.RENT, RentPeriod.MONTH)

    if normalized in {"rent_day", "daily_rent"}:
        return (ApartmentDealType.RENT, RentPeriod.DAY)

    raise UnsupportedOfferTypeError(
        f"Unsupported offer_type: {offer_type!r}"
    )

def map_apartment_record(record: HousingApartmentRecord) -> ApartmentSeedData:
    deal_type, rent_period = map_offer_type(record.offer_type)

    return ApartmentSeedData(
        dataset_id=record.id,
        external_id=record.external_id,
        title=record.title,
        price=record.price,
        currency=record.currency,
        deal_type=deal_type,
        rent_period=rent_period,
        area=record.area,
        rooms=record.rooms,
        floor=record.floor,
        total_floors=record.floors_total,
        building_year=record.building_year,
        address=record.address,
        latitude=record.lat,
        longitude=record.lon,
        coordinate_method=record.coordinate_method,
        district_assignment_method=record.district_assignment_method,
        district_source_id=record.district_source_id,
        district_name=record.district_name,
        complex_source_id=record.complex_source_id,
        complex_name=record.complex_name,
        complex_source_url=record.complex_source_url,
        market_type=record.market_type,
        offer_type=record.offer_type,
        origin=ApartmentOrigin.SEED,
        source=record.source,
        source_id=record.source_id,
        source_url=record.source_url,
        source_updated_at=record.source_updated_at,
        collected_at=record.collected_at,
        raw_sha256=record.raw_sha256,
        is_demo=record.is_demo,
        status=ApartmentStatus.PUBLISHED,
    )
