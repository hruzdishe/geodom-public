from datetime import datetime
from decimal import Decimal
from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from geodom_backend.apartments.enums import (
    ApartmentDealType,
    ApartmentFeatureStatus,
    ApartmentStatus,
    RentPeriod,
)
from geodom_backend.districts.schemas import DistrictResponse


class ApartmentPhotoResponse(BaseModel):
    id: int

    position: int
    is_cover: bool

    width: int | None = None
    height: int | None = None

    mime_type: str | None = None
    size_bytes: int | None = None

    url: str | None = None

    model_config = ConfigDict(
        from_attributes=True
    )

class ApartmentResponse(BaseModel):
    id: int

    title: str

    price: Decimal
    currency: str

    deal_type: ApartmentDealType
    rent_period: RentPeriod | None

    rooms: int
    area: Decimal

    floor: int
    total_floors: int

    address: str
    latitude: Decimal | None
    longitude: Decimal | None
    owner_id: int | None
    house_number: str | None
    origin: str
    source: str
    source_url: str | None
    complex_name: str | None
    building_year: int | None
    status: ApartmentStatus
    district: DistrictResponse

    photos: list[ApartmentPhotoResponse]
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )

class ApartmentListResponse(BaseModel):
    items: list[ApartmentResponse]

    total: int
    limit: int
    offset: int

class ApartmentCreateRequest(BaseModel):
    title: str = Field(
        min_length=3,
        max_length=255
    )

    price: Decimal = Field(gt=0)

    deal_type: ApartmentDealType

    rent_period: RentPeriod | None = None

    rooms: int = Field(ge=0, le=20)

    area: Decimal = Field(gt=0, le=10_000)

    floor: int = Field(ge=0)

    total_floors: int = Field(ge=1)

    address: str = Field(
        min_length=5,
        max_length=512
    )

    description: str | None = Field(
        default=None,
        max_length=10_000
    )

    building_year: int | None = Field(
        default=None,
        ge=1700,
        le=2200
    )

    @model_validator(mode="after")
    def validate_deal(self) -> Self:
        if self.deal_type == ApartmentDealType.SALE:
            if self.rent_period is not None: raise ValueError(
                "rent_period must be empty for sale listings"
            )

        if self.deal_type == ApartmentDealType.RENT and self.rent_period is None:
            raise ValueError("rent_period is required for rental listings")

        return self

    @model_validator(mode="after")
    def validate_floors(self) -> Self:
        if self.floor > self.total_floors:
            raise ValueError("floor cannot be greater then total_floors")

        return self

class ApartmentFilters(BaseModel):
    deal_type: ApartmentDealType | None = None
    rent_period: RentPeriod | None = None

    price_min: Decimal | None = Field(
        default=None,
        ge=0
    )

    price_max: Decimal | None = Field(
        default=None,
        ge=0
    )

    rooms: int | None = Field(
        default=None,
        ge=0
    )

    district_id: int | None = Field(
        default=None,
        gt=0
    )

    @model_validator(mode="after")
    def validate_filters(self) -> Self:
        if self.price_min is not None and self.price_max is not None and self.price_min > self.price_max:
            raise ValueError("price_min cannot be greater than price_max")

        if self.rent_period is not None and self.deal_type != ApartmentDealType.RENT:
            raise ValueError("rent_period can only be used with deal_type=rent")

        return self

class ApartmentUpdateRequest(BaseModel):
    NON_NULLABLE_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "title",
            "price",
            "deal_type",
            "rooms",
            "area",
            "floor",
            "total_floors",
            "address",
        }
    )

    title: str | None = Field(
        default=None,
        min_length=3,
        max_length=255
    )

    price: Decimal | None = Field(
        default=None,
        gt=0
    )

    deal_type: ApartmentDealType | None = None

    rent_period: RentPeriod | None = None

    rooms: int | None = Field(default=None, ge=0, le=20)
    area: Decimal | None = Field(default=None, gt=0, le=10_000)
    floor: int | None = Field(default=None, ge=0)
    total_floors: int | None = Field(default=None, ge=1)
    address: str | None = Field(default=None, min_length=5, max_length=512)
    description: str | None = Field(default=None, max_length=10_000)
    building_year: int | None = Field(
        default=None,
        ge=1700,
        le=2200
    )

    @model_validator(mode="after")
    def validate_nullabel_fields(self) -> Self:
        for field_name in self.NON_NULLABLE_FIELDS:
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")

        return self

class ApartmentFeaturesResponse(BaseModel):
    status: ApartmentFeatureStatus

    schools_1km: int | None
    kindergartens_1km: int | None
    parks_1km: int | None
    shops_1km: int | None
    transport_stops_1km: int | None

    nearest_school_m: Decimal | None
    nearest_kindergarten_m: Decimal | None
    nearest_park_m: Decimal | None
    nearest_transport_m: Decimal | None

    feature_version: str | None

    model_config = ConfigDict(from_attributes=True)

class ApartmentDetailResponse(ApartmentResponse):
    description: str | None
    features: ApartmentFeaturesResponse | None
