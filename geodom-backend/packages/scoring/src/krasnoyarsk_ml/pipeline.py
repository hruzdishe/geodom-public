import argparse
import hashlib
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pyarrow.parquet as pq

from .config import Settings
from .normalize import normalize
from .osm import CollectionError, build_query, fetch

logger = logging.getLogger(__name__)


def atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temp.write_bytes(content)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def write_json(path: Path, value: dict) -> None:
    atomic_bytes(path, json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8"))


def collect(settings: Settings, query: str | None = None, collection: str = "osm") -> Path:
    now = datetime.now(UTC)
    query = query or build_query(settings.query_timeout_seconds)
    content = fetch(settings, query)
    # Preserve each download before parsing; daily file is the latest snapshot.
    archive = (
        settings.data_dir / "raw" / collection / now.strftime("%Y-%m-%d") / f"{uuid4().hex}.json"
    )
    atomic_bytes(archive, content)
    metadata = {
        "collected_at": now.isoformat(),
        "endpoint": str(settings.overpass_url),
        "query": query,
        "sha256": hashlib.sha256(content).hexdigest(),
        "source": "openstreetmap",
        "license": "ODbL-1.0",
        "attribution": "© OpenStreetMap contributors",
        "archive": str(archive),
    }
    write_json(archive.with_suffix(".metadata.json"), metadata)
    from .osm import check_payload

    payload = json.loads(content)
    check_payload(payload)
    metadata["timestamp_osm_base"] = payload.get("osm3s", {}).get("timestamp_osm_base")
    write_json(archive.with_suffix(".metadata.json"), metadata)
    daily = settings.data_dir / "raw" / collection / f"{now:%Y-%m-%d}.json"
    atomic_bytes(daily, content)
    write_json(daily.with_suffix(".metadata.json"), metadata)
    return daily


def preprocess(settings: Settings, raw: Path) -> dict:
    metadata = json.loads(raw.with_suffix(".metadata.json").read_text(encoding="utf-8"))
    content = raw.read_bytes()
    if hashlib.sha256(content).hexdigest() != metadata["sha256"]:
        raise CollectionError("Raw checksum mismatch")
    table, report = normalize(json.loads(content), datetime.fromisoformat(metadata["collected_at"]))
    report.update(raw_path=str(raw), raw_sha256=metadata["sha256"])
    base_timestamp = metadata.get("timestamp_osm_base")
    report["timestamp_osm_base"] = base_timestamp
    if base_timestamp:
        age_days = (
            datetime.fromisoformat(metadata["collected_at"])
            - datetime.fromisoformat(base_timestamp)
        ).total_seconds() / 86400
        report["source_age_days_at_collection"] = round(age_days, 2)
        if age_days > 7:
            report["warnings"].append(f"Overpass snapshot is {age_days:.0f} days old.")
    processed = settings.data_dir / "processed"
    write_json(processed / "validation_report.json", report)
    if not table.num_rows:
        raise CollectionError("No valid POIs; previous Parquet was preserved")
    target = processed / "geo_objects.parquet"
    temp = target.with_name(f".{uuid4().hex}.parquet")
    try:
        pq.write_table(table, temp, compression="zstd")
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)
    write_json(processed / "geo_objects.metadata.json", metadata | {"rows": table.num_rows})
    counts = report["subcategory_counts"]
    groups = {
        "schools": ["school"],
        "kindergartens": ["kindergarten"],
        "parks": ["park"],
        "hospitals": ["hospital"],
        "clinics": ["clinic"],
        "pharmacies": ["pharmacy"],
        "shops": ["supermarket", "mall"],
        "sport": ["sports_centre", "fitness_centre"],
        "transport": ["bus_stop", "tram_stop", "station"],
    }
    for label, members in groups.items():
        print(f"{label}: {sum(counts.get(member, 0) for member in members)}")
    print(f"total: {table.num_rows}\nparquet: {target.resolve()}")
    # Reuse the downloaded reference offline on subsequent POI normalization runs.
    address_snapshots = sorted(
        path
        for path in (settings.data_dir / "raw/osm_addresses").glob("*.json")
        if len(path.stem) == 10
    )
    if address_snapshots:
        from .addresses import enrich_file

        enriched = enrich_file(
            settings, address_snapshots[-1], settings.max_address_m, settings.max_street_m
        )
        report["address_enrichment_methods"] = enriched["methods"]
        report["records_with_address"] = table.num_rows - enriched["methods"].get("missing", 0)
        write_json(processed / "validation_report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Krasnoyarsk OSM data pipeline")
    parser.add_argument("stage", choices=["collect", "normalize", "osm"])
    parser.add_argument("--raw", type=Path, help="Saved raw snapshot for offline normalization")
    args = parser.parse_args()
    if args.stage == "normalize" and args.raw is None:
        parser.error("normalize requires --raw")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = Settings()
    run = {
        "started_at": datetime.now(UTC).isoformat(),
        "source": "openstreetmap",
        "stage": args.stage,
        "errors": [],
        "records_received": 0,
        "records_valid": 0,
        "records_invalid": 0,
        "records_inserted": 0,
        "records_updated": 0,
        "storage_mode": "snapshot_replace; no database insert/update",
    }
    code = 0
    try:
        raw = collect(settings) if args.stage in {"collect", "osm"} else args.raw
        logger.info("Raw snapshot: %s", raw)
        if args.stage != "collect":
            run.update(preprocess(settings, raw))
        else:
            run["records_received"] = len(json.loads(raw.read_bytes())["elements"])
    except Exception as exc:
        logger.exception("Pipeline failed")
        run["errors"].append(str(exc))
        code = 1
    finally:
        run["finished_at"] = datetime.now(UTC).isoformat()
        write_json(settings.data_dir / "reports" / f"{uuid4().hex}.json", run)
        logger.info("Run summary: %s", json.dumps(run, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
