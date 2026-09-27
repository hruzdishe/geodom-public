"""Offline re-normalization, referential/file integrity checks, and portable bundle."""

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pyarrow.parquet as pq
from PIL import Image

from ..pipeline import atomic_bytes, write_json
from .collector import write_parquet
from .preview import render_preview
from .sibdom import DISTRICTS, parse_listing


def prepare(root: Path, output: Path, expected: int = 300) -> dict:
    processed = root / "processed/housing"
    report = json.loads((processed / "collection_report.json").read_text(encoding="utf-8"))
    if report["status"] != "complete":
        raise ValueError("Collection is not complete; inspect collection_report.json")
    apartments = pq.read_table(processed / "apartments.parquet").to_pylist()
    media = pq.read_table(processed / "media.parquet").to_pylist()
    if len(apartments) != expected or len({a["id"] for a in apartments}) != expected:
        raise ValueError("Unexpected apartment count or duplicate IDs")
    # Reparse only selected source pages; no network and no repeat image downloads.
    normalized = []
    for old in apartments:
        key = hashlib.sha256(old["source_url"].encode()).hexdigest()
        raw = root / "raw/housing/sibdom" / f"{key}.bin"
        raw_meta = json.loads(raw.with_suffix(".json").read_text(encoding="utf-8"))
        content = raw.read_bytes()
        if hashlib.sha256(content).hexdigest() != old["raw_sha256"]:
            raise ValueError(f"Raw checksum mismatch: {old['id']}")
        parsed = parse_listing(
            content.decode("utf-8"),
            old["source_url"],
            datetime.fromisoformat(raw_meta["collected_at"]),
            old["raw_sha256"],
        )
        normalized.append(
            parsed.model_dump()
            | {
                "cover_storage_key": old["cover_storage_key"],
                "photo_count": old["photo_count"],
            }
        )
    apartments = normalized
    ids = {a["id"] for a in apartments}
    if len({m["id"] for m in media}) != len(media):
        raise ValueError("Duplicate media IDs")
    files = []
    for photo in media:
        if photo["entity_id"] not in ids:
            raise ValueError("Orphan media row")
        path = (root / photo["local_path"]).resolve()
        if not path.is_relative_to((root / "media").resolve()):
            raise ValueError("Unsafe media path")
        if hashlib.sha256(path.read_bytes()).hexdigest() != photo["sha256"]:
            raise ValueError(f"Photo checksum mismatch: {path}")
        with Image.open(path) as image:
            if image.format != "WEBP" or image.size != (photo["width"], photo["height"]):
                raise ValueError(f"Invalid photo format/dimensions: {path}")
            image.verify()
        files.append(path)
    for apartment in apartments:
        photos = [m for m in media if m["entity_id"] == apartment["id"]]
        if len(photos) != apartment["photo_count"] or not photos:
            raise ValueError("Apartment photo count mismatch")
        covers = [m for m in photos if m["is_cover"]]
        if len(covers) != 1 or covers[0]["storage_key"] != apartment["cover_storage_key"]:
            raise ValueError("Cover reference mismatch")
        if sorted(m["position"] for m in photos) != list(range(len(photos))):
            raise ValueError("Photo order has gaps")
    counts = Counter(a["district_name"] for a in apartments)
    if expected >= 7 and set(counts) != set(DISTRICTS.values()):
        raise ValueError("Not all districts covered")
    manifest = {
        "dataset_version": "housing_sibdom_v1",
        "exported_at": datetime.now(UTC).isoformat(),
        "source": "sibdom",
        "apartments": len(apartments),
        "photos": len(media),
        "district_counts": dict(counts),
        "photo_bytes": sum(p.stat().st_size for p in files),
        "unique_photo_hashes": len({m["sha256"] for m in media}),
        "unique_locations_4dp": len({(round(a["lat"], 4), round(a["lon"], 4)) for a in apartments}),
        "price_range_rub": [
            min(a["price"] for a in apartments),
            max(a["price"] for a in apartments),
        ],
        "room_counts": dict(Counter(str(a["rooms"]) for a in apartments)),
        "validation": "all_ids_links_cover_files_hashes_formats_checked",
        "district_method": "listing_address_tag_not_spatial_join",
        "photo_rights": "not_verified_for_republication; preserve attribution and publication_allowed",
        "storage": {
            "database": "PostgreSQL (future import)",
            "object_store": "MinIO (future upload)",
            "bucket": "housing-media",
            "key_column": "storage_key",
        },
    }
    write_parquet(processed / "apartments.parquet", apartments)
    for name, rows in [("apartments", apartments), ("media", media)]:
        atomic_bytes(
            processed / f"{name}.jsonl",
            "".join(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in rows).encode(),
        )
    write_json(processed / "dataset_manifest.json", manifest)
    atomic_bytes(processed / "preview.html", render_preview(apartments, media).encode("utf-8"))
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(".tmp")
    try:
        with ZipFile(temp, "w", ZIP_DEFLATED, compresslevel=1) as archive:
            for path in sorted(processed.glob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(root).as_posix())
            for path in files:
                archive.write(path, path.relative_to(root.resolve()).as_posix())
        with ZipFile(temp) as archive:
            if archive.testzip() is not None:
                raise ValueError("Archive integrity check failed")
        temp.replace(output)
    finally:
        temp.unlink(missing_ok=True)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and package collected housing for transfer"
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=Path("data/exports/housing_bundle.zip"))
    parser.add_argument("--expected", type=int, default=300)
    args = parser.parse_args()
    print(
        json.dumps(prepare(args.data_dir, args.output, args.expected), ensure_ascii=False, indent=2)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
