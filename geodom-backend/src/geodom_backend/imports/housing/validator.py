import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from geodom_backend.imports.housing.reader import HousingSnapshot
from geodom_backend.imports.housing.schemas import HousingMediaRecord


class HousingSnapshotValidationError(ValueError):
    def __init__(self, issues: list[str]):
        self.issues = issues

        message = (
            "Housing snapshot validation failed:\n"
            + "\n".join(f"- {issue}" for issue in issues)
        )

        super().__init__(message)

@dataclass(frozen=True, slots=True)
class HousingSnapshotValidationReport:
    apartments: int
    media: int
    districts: int
    total_media_bytes: int

class HousingSnapshotValidator:
    def validate(self, snapshot: HousingSnapshot, *, validate_files: bool = False) -> HousingSnapshotValidationReport:
        issues: list[str] = []
        self._validate_manifest(snapshot, issues)
        self._validate_apartments(snapshot, issues)
        self._validate_media(snapshot, issues)
        self._validate_relations(snapshot, issues)

        if validate_files:
            self._validate_media_files(snapshot, issues)

        if issues:
            raise HousingSnapshotValidationError(issues)

        districts = {
            apartment.district_source_id for apartment in snapshot.apartments
        }

        return HousingSnapshotValidationReport(
            apartments=len(snapshot.apartments),
            media=len(snapshot.media),
            districts=len(districts),
            total_media_bytes=sum(
                media.size_bytes for media in snapshot.media
            )
        )

    @staticmethod
    def _validate_manifest(snapshot: HousingSnapshot, issues: list[str]):
        manifest = snapshot.manifest
        apartments = snapshot.apartments
        media = snapshot.media

        allowed_validation_statuses = {
            "ok",
            "all_ids_links_cover_files_hashes_formats_checked"
        }

        if manifest.validation not in allowed_validation_statuses:
            issues.append(
                f"Unsupported dataset manifest validation status: {manifest.validation!r}"
            )

        if len(apartments) != manifest.apartments:
            issues.append(
                "Apartment count mismatch: "
                f"manifest={manifest.apartments}, actual={len(apartments)}"
            )

        if len(media) != manifest.photos:
            issues.append(
                "Media count mismatch: "
                f"manifest={manifest.photos}, actual={len(media)}"
            )

        total_media_bytes = sum(
            item.size_bytes for item in media
        )

        if total_media_bytes != manifest.photo_bytes:
            issues.append(
                "Media bytes mismatch: "
                f"manifest={manifest.photo_bytes}, actual={total_media_bytes}"
            )

        unique_hashes = len({item.sha256 for item in media})
        if unique_hashes != manifest.unique_photo_hashes:
            issues.append(
                "Unique photo hashed mismatch: "
                f"manifest={manifest.unique_photo_hashes}, actual={unique_hashes}"
            )

        district_counts = dict(
            Counter(apartment.district_name for apartment in apartments)
        )
        if district_counts != manifest.district_counts:
            issues.append(
                "district counts do not match manifest"
            )

        room_counts = dict(
            Counter(str(apartment.rooms) for apartment in apartments)
        )
        if room_counts != manifest.room_counts:
            issues.append("Room counts do not match manifest")

        if apartments:
            prices = [
                apartment.price for apartment in apartments
            ]

            actual_price_range = (
                int(min(prices)),
                int(max(prices))
            )
            if actual_price_range != manifest.price_range_rub:
                issues.append(
                    "Price range mismatch: "
                    f"manifest={manifest.price_range_rub}, actual={actual_price_range}"
                )

        unique_locations = {
            (
                apartment.lat.quantize(Decimal("0.0001")),
                apartment.lon.quantize(Decimal("0.0001"))
            )
            for apartment in apartments
        }
        if len(unique_locations) != manifest.unique_locations_4dp:
            issues.append(
                "Unique location count mismatch: "
                f"manifest={manifest.unique_locations_4dp}, "
                f"actual={len(unique_locations)}"
            )

    @staticmethod
    def _validate_counts(snapshot: HousingSnapshot, issues: list[str]):
        manifest = snapshot.manifest
        apartment_count = len(snapshot.apartments)
        media_count = len(snapshot.media)

        if apartment_count != manifest.apartments:
            issues.append(
                "Apartment count mismatch: "
                f"manifest={manifest.apartments}, "
                f"actual={apartment_count}"
            )

        if media_count != manifest.photos:
            issues.append(
                "Media count mismatch: "
                f"manifest={manifest.photos}, "
                f"actual={media_count}"
            )

        media_bytes = sum(media.size_bytes for media in snapshot.media)

        if media_bytes != manifest.photo_bytes:
            issues.append(
                "Media bytes mismatch: "
                f"manifest={manifest.photo_bytes}, "
                f"actual={media_bytes}"
            )

    @staticmethod
    def _validate_apartments(snapshot: HousingSnapshot, issues: list[str]):
        ids: set[str] = set()
        natural_keys: set[tuple[str, str]] = set()
        districts: dict[str, str] = {}

        for apartment in snapshot.apartments:
            if apartment.id in ids:
                issues.append(
                    "Duplicate apartment id: "
                    f"{apartment.id}"
                )

            ids.add(apartment.id)

            natural_key = (
                apartment.source, apartment.source_id
            )

            if natural_key in natural_keys:
                issues.append(
                    "Duplicate apartment natural key: "
                    f"{natural_key}"
                )

            natural_keys.add(natural_key)

            if apartment.source != snapshot.manifest.source:
                issues.append(
                    "Unexpected source for "
                    f"{apartment.id}: "
                    f"{apartment.source}"
                )

            existing_name = districts.get(apartment.district_source_id)
            if existing_name is not None and existing_name != apartment.district_name:
                issues.append(
                    "District source id points to "
                    "multiple names: "
                    f"{apartment.district_source_id}"
                )

            districts[apartment.district_source_id] = apartment.district_name

    @staticmethod
    def _validate_media(snapshot: HousingSnapshot, issues: list[str]):
        media_ids: set[str] = set()
        storage_keys: set[tuple[str, str]] = set()

        for media in snapshot.media:
            if media.id in media_ids:
                issues.append(
                    "Duplicate media id: "
                    f"{media.id}"
                )

            media_ids.add(media.id)

            storage_key = (media.bucket, media.storage_key)
            if storage_key in storage_keys:
                issues.append(
                    "Duplicate media storage key: "
                    f"{storage_key}"
                )

            storage_keys.add(storage_key)

            if media.bucket != snapshot.manifest.storage.bucket:
                issues.append(
                    "Unexpected bucket for "
                    f"{media.id}: {media.bucket}"
                )

            if media.source != snapshot.manifest.source:
                issues.append(f"Unexpected source for {media.id}: {media.source}")

    @staticmethod
    def _validate_relations(snapshot: HousingSnapshot, issues: list[str]):
        apartments_by_id = {apartment.id: apartment for apartment in snapshot.apartments}

        media_by_apartment: dict[str, list[HousingMediaRecord]] = defaultdict(list)
        for media in snapshot.media:
            if media.entity_id not in apartments_by_id:
                issues.append(
                    f"Media {media.id} references unknown apartment {media.entity_id}"
                )
                continue

            media_by_apartment[media.entity_id].append(media)

        for apartment in snapshot.apartments:
            media_items = media_by_apartment.get(apartment.id, [])
            if len(media_items) != apartment.photo_count:
                issues.append(
                    f"Photo count mismatch for {apartment.id}: "
                    f"apartment={apartment.photo_count}, media={len(media_items)}"
                )

            positions = sorted(item.position for item in media_items)
            expected_positions = list(range(len(media_items)))
            if positions != expected_positions:
                issues.append(
                    f"Non-contiguous media positions for {apartment.id}: {positions}"
                )

            covers = [
                item for item in media_items if item.is_cover
            ]
            if len(covers) != 1:
                issues.append(
                    f"Apartment {apartment.id} must have exactly one cover, "
                    f"found {len(covers)}"
                )
                continue

            if covers[0].storage_key != apartment.cover_storage_key:
                issues.append(
                    f"Cover storage key mismatch for {apartment.id}"
                )

    @staticmethod
    def _validate_media_files(snapshot: HousingSnapshot, issues: list[str]):
        for media in snapshot.media:
            path = snapshot.paths.resolve_media_file(media.local_path)
            if not path.is_file():
                issues.append(
                    f"Media file not found: {path}"
                )
                continue

            size = path.stat().st_size
            if size != media.size_bytes:
                issues.append(
                    f"Media size mismatch for {media.id}"
                    f"expected={media.size_bytes}, actual={size}"
                )
                continue

            sha256 = (
                HousingSnapshotValidator._calculate_sha256(path)
            )
            if sha256 != media.sha256:
                issues.append(
                    f"Media SHA-256 mismatch for {media.id}"
                )

    @staticmethod
    def _calculate_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            while chunk := file.read(1024 * 1024):
                digest.update(chunk)
            return digest.hexdigest()
