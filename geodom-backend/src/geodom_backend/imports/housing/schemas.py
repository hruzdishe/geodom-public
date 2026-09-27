from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

class SnapshotBaseModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

class HousingApartmentRecord(SnapshotBaseModel):
    id: str
    external_id: str

    title: str

    price: Decimal
    price_m2: Decimal
    currency: str

    area: Decimal
    rooms: int
    floor: int
    floors_total: int

    building_year: int | None

    address: str

    lat: Decimal
    lon: Decimal
    coordinate_method: str

    district_name: str
    district_source_id: str
    district_assignment_method: str

    complex_source_id: str | None
    complex_name: str | None
    complex_source_url: str | None

    market_type: str
    offer_type: str

    source: str
    source_id: str
    source_url: str

    source_updated_at: datetime | None
    collected_at: datetime

    raw_sha256: str
    is_demo: bool

    image_urls: list[str]
    cover_storage_key: str
    photo_count: int

class HousingMediaRecord(SnapshotBaseModel):
    id: str

    entity_type: Literal["apartment"]
    entity_id: str

    storage_key: str
    bucket: str
    local_path: str

    source: str
    source_url: str
    listing_url: str

    position: int
    is_cover: bool

    width: int
    height: int
    mime_type: str

    size_bytes: int = Field(
        validation_alias="bytes",
        serialization_alias="bytes"
    )

    sha256: str
    original_sha256: str

    created_at: datetime

    license: str | None
    rights_status: str
    attribution: str

    publication_allowed: bool
    image_kind: str

class HousingStorageManifest(SnapshotBaseModel):
    database: str
    object_store: str
    bucket: str
    key_column: str

class HousingDatasetManifest(SnapshotBaseModel):
    dataset_version: str
    exported_at: datetime

    source: str

    apartments: int
    photos: int

    district_counts: dict[str, int]

    photo_bytes: int
    unique_photo_hashes: int
    unique_locations_4dp: int

    price_range_rub: tuple[int, int]
    room_counts: dict[str, int]

    validation: str
    district_method: str
    photo_rights: str

    storage: HousingStorageManifest
