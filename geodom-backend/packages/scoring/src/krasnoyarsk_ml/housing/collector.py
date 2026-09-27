import argparse
import hashlib
import io
import json
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq
from PIL import Image, ImageOps

from ..pipeline import atomic_bytes, write_json
from .http import DownloadError, RawClient
from .sibdom import (
    DISTRICTS,
    PARSER_VERSION,
    START,
    district_links,
    listing_urls,
    page_count,
    parse_listing,
    secondary_url,
)

logger = logging.getLogger(__name__)


def collect_candidate(
    client: RawClient,
    root: Path,
    url: str,
    slug: str,
    max_photos: int,
    occupied: dict,
    known: set,
    max_per_building: int,
):
    """Bounded worker; quota/dedup decisions remain deterministic in the main thread."""
    try:
        body, raw_meta = client.read(url)
        apartment = parse_listing(
            body.decode("utf-8"),
            url,
            datetime.fromisoformat(raw_meta["collected_at"]),
            raw_meta["sha256"],
        )
        if apartment.district_source_id != slug:
            raise ValueError("District in card differs from selected district")
        building = (round(apartment.lat, 4), round(apartment.lon, 4))
        if occupied.get(building, 0) >= max_per_building:
            raise ValueError("Per-building diversity cap")
        signature = (
            *building,
            apartment.floor,
            apartment.rooms,
            round(apartment.area, 1),
            apartment.price,
        )
        if signature in known:
            raise ValueError("Likely duplicate listing (location, floor, rooms, area, price)")
        row, photos, errors = apartment.model_dump(), [], []

        def download(item):
            pos, photo_url = item
            try:
                return save_photo(client, root, row, photo_url, pos), None
            except (DownloadError, ValueError, OSError) as exc:
                return None, {"source_url": photo_url, "reason": str(exc)}

        with ThreadPoolExecutor(max_workers=2) as pool:
            for photo, error in pool.map(download, enumerate(row["image_urls"][:max_photos])):
                if photo and photo["sha256"] not in {p["sha256"] for p in photos}:
                    photos.append(photo)
                if error:
                    errors.append(error)
        if not photos:
            return None, [], errors + [{"source_url": url, "reason": "No valid local photo"}]
        for pos, photo in enumerate(photos):
            photo.update(position=pos, is_cover=pos == 0)
        row.update(cover_storage_key=photos[0]["storage_key"], photo_count=len(photos))
        return row, photos, errors
    except (DownloadError, ValueError, KeyError, TypeError) as exc:
        return None, [], [{"source_url": url, "reason": str(exc)}]


def write_parquet(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"No rows for {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows)
    # Keep nullable columns typed for PostgreSQL import even if all values are absent.
    types = {
        "source_updated_at": pa.timestamp("us", tz="UTC"),
        "building_year": pa.int64(),
        "complex_source_id": pa.string(),
        "complex_source_url": pa.string(),
        "complex_name": pa.string(),
        "license": pa.string(),
    }
    for name, dtype in types.items():
        if name in table.column_names:
            i = table.column_names.index(name)
            table = table.set_column(i, name, table[name].cast(dtype))
    temp = path.with_name(f".{uuid4().hex}.parquet")
    try:
        pq.write_table(table, temp, compression="zstd")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def save_photo(client: RawClient, root: Path, apartment: dict, url: str, position: int) -> dict:
    content, meta = client.read(url)
    with Image.open(io.BytesIO(content)) as image:
        if image.width * image.height > 40_000_000 or min(image.size) < 100:
            raise ValueError("Image resolution invalid")
        image.load()
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((1600, 1600))
        stream = io.BytesIO()
        image.save(stream, format="WEBP", quality=86)
        output = stream.getvalue()
        width, height = image.size
    digest = hashlib.sha256(output).hexdigest()
    key = f"apartments/sibdom/{apartment['source_id']}/{digest}.webp"
    # Different source URLs can be identical images; avoid concurrent replacement on Windows.
    with client.lock:
        destination = root / "media" / key
        if (
            not destination.exists()
            or hashlib.sha256(destination.read_bytes()).hexdigest() != digest
        ):
            atomic_bytes(destination, output)
    return {
        "id": f"sibdom:{apartment['source_id']}:{digest}",
        "entity_type": "apartment",
        "entity_id": apartment["id"],
        "storage_key": key,
        "bucket": "housing-media",
        "local_path": "media/" + key,
        "source": "sibdom",
        "source_url": url,
        "listing_url": apartment["source_url"],
        "position": position,
        "is_cover": position == 0,
        "width": width,
        "height": height,
        "mime_type": "image/webp",
        "bytes": len(output),
        "sha256": digest,
        "original_sha256": meta["sha256"],
        "created_at": datetime.fromisoformat(meta["collected_at"]),
        "license": None,
        "rights_status": "not_verified_for_republication",
        "attribution": "СИБДОМ — " + apartment["source_url"],
        "publication_allowed": False,
        "image_kind": "listing_gallery_unclassified",
    }


def run(
    root: Path,
    target: int,
    max_photos: int,
    max_pages: int,
    offline: bool,
    delay: float,
    max_per_building: int,
    workers: int = 4,
    restart: bool = False,
    allow_uneven: bool = False,
) -> dict:
    started = datetime.now(UTC).isoformat()
    report = {
        "started_at": started,
        "source": "sibdom",
        "target": target,
        "parser_version": PARSER_VERSION,
        "errors": [],
        "rejected": [],
        "network_or_media_errors": [],
        "district_counts": {},
        "status": "running",
        "warnings": [
            "Districts are source labels; spatial verification is pending.",
            "Map points may be approximate building locations.",
            "Listing galleries may contain floorplans, exterior photos, or renders.",
            "Photo republication rights have not been verified; publication_allowed=false.",
            "A district-balanced convenience sample is not representative of market prices.",
        ],
    }
    apartments, media, seen, signatures = [], [], set(), set()
    building_counts = Counter()
    outputs = root / "processed/housing"
    outputs.mkdir(parents=True, exist_ok=True)
    previous_report = outputs / "collection_report.json"
    if not restart and previous_report.exists():
        previous = json.loads(previous_report.read_text(encoding="utf-8"))
        if previous.get("target") == target and (outputs / "apartments.parquet").exists():
            apartments = pq.read_table(outputs / "apartments.parquet").to_pylist()
            media = pq.read_table(outputs / "media.parquet").to_pylist()
            report["rejected"] = previous.get("rejected", [])
            if previous.get("parser_version") != PARSER_VERSION:
                report["previous_rejection_count"] = len(report["rejected"])
                report["rejected"] = []
            report["network_or_media_errors"] = previous.get("network_or_media_errors", [])
            report["initial_started_at"] = previous.get(
                "initial_started_at", previous["started_at"]
            )
            seen.update(a["source_url"] for a in apartments)
            seen.update(
                r["source_url"]
                for r in report["rejected"]
                if r["reason"] != "District in card differs from selected district"
            )
            for row in apartments:
                building = (round(row["lat"], 4), round(row["lon"], 4))
                building_counts[building] += 1
                signatures.add(
                    (*building, row["floor"], row["rooms"], round(row["area"], 1), row["price"])
                )
            logger.info(
                "Resuming saved dataset: %d apartments, %d photos", len(apartments), len(media)
            )

    def checkpoint():
        report.update(
            records_received=len(seen),
            records_valid=len(apartments),
            photos_valid=len(media),
            district_counts=dict(Counter(a["district_name"] for a in apartments)),
        )
        write_json(outputs / "collection_report.json", report)
        if apartments:
            write_parquet(outputs / "apartments.parquet", apartments)
        if media:
            write_parquet(outputs / "media.parquet", media)

    with RawClient(root / "raw/housing/sibdom", delay=delay, offline=offline) as client:
        try:
            html, _ = client.read(START)
            districts = district_links(html.decode("utf-8"))
            secondary_districts = {}
            secondary_start = secondary_url(html.decode("utf-8"))
            if secondary_start:
                secondary_html, _ = client.read(secondary_start)
                secondary_districts = district_links(secondary_html.decode("utf-8"))
            # Prime robots once before threads share the downloader.
            for host in range(6):
                client.check_robots(f"https://img{host}.sibdom.ru/")
            district_plan = list(enumerate(DISTRICTS.items()))
            if allow_uneven:
                district_plan += [(None, district) for district in DISTRICTS.items()]
            for district_index, (slug, district_name) in district_plan:
                if len(apartments) >= target:
                    break
                count = sum(a["district_source_id"] == slug for a in apartments)
                quota = (
                    count + target - len(apartments)
                    if district_index is None
                    else target // 7 + int(district_index < target % 7)
                )
                if quota == 0:
                    continue
                if count >= quota:
                    continue
                district_html, _ = client.read(districts[slug])
                secondary = secondary_districts.get(slug) or secondary_url(
                    district_html.decode("utf-8")
                )
                pages = [secondary, districts[slug]] if secondary else [districts[slug]]
                for base in dict.fromkeys(pages):
                    source_pages = max_pages
                    for page in range(1, max_pages + 1):
                        if count >= quota or page > source_pages:
                            break
                        page_url = base if page == 1 else base + "?" + urlencode({"page": page})
                        page_body, _ = client.read(page_url)
                        if page == 1:
                            source_pages = page_count(page_body.decode("utf-8"))
                        urls = listing_urls(page_body.decode("utf-8"))
                        fresh = [u for u in urls if u not in seen]
                        if not urls:
                            break
                        if not fresh:
                            continue
                        cursor = 0
                        with ThreadPoolExecutor(max_workers=workers) as candidates:
                            while cursor < len(fresh) and count < quota:
                                batch = fresh[cursor : cursor + min(workers, quota - count)]
                                cursor += len(batch)
                                seen.update(batch)
                                futures = [
                                    candidates.submit(
                                        collect_candidate,
                                        client,
                                        root,
                                        url,
                                        slug,
                                        max_photos,
                                        dict(building_counts),
                                        set(signatures),
                                        max_per_building,
                                    )
                                    for url in batch
                                ]
                                for url, future in zip(batch, futures):
                                    row, photos, problems = future.result()
                                    if row is None:
                                        report["rejected"].extend(problems)
                                        if any(
                                            p["reason"]
                                            == "District in card differs from selected district"
                                            for p in problems
                                        ):
                                            seen.discard(url)
                                        continue
                                    report["network_or_media_errors"].extend(problems)
                                    building = (round(row["lat"], 4), round(row["lon"], 4))
                                    signature = (
                                        *building,
                                        row["floor"],
                                        row["rooms"],
                                        round(row["area"], 1),
                                        row["price"],
                                    )
                                    reason = None
                                    if building_counts[building] >= max_per_building:
                                        reason = "Per-building diversity cap"
                                    elif signature in signatures:
                                        reason = "Likely duplicate listing (location, floor, rooms, area, price)"
                                    if reason:
                                        report["rejected"].append(
                                            {"source_url": url, "reason": reason}
                                        )
                                        continue
                                    apartments.append(row)
                                    media.extend(photos)
                                    signatures.add(signature)
                                    building_counts[building] += 1
                                    count += 1
                                    checkpoint()
                                    logger.info(
                                        "%s %d/%d | total %d/%d | photos %d",
                                        district_name,
                                        count,
                                        quota,
                                        len(apartments),
                                        target,
                                        len(media),
                                    )
            report["sampling_mode"] = "districts_then_fill" if allow_uneven else "district_quotas"
            if len(apartments) < target:
                report["errors"].append(f"Collected {len(apartments)} of requested {target}")
            report["status"] = "complete" if len(apartments) == target else "partial"
        except Exception as exc:
            report["errors"].append(str(exc))
            report["status"] = "failed"
            logger.exception("Housing collection failed")
        finally:
            report["finished_at"] = datetime.now(UTC).isoformat()
            checkpoint()
    # JSON manifests are portable and directly usable by a future DB/S3 import job.
    if apartments:
        atomic_bytes(
            outputs / "apartments.jsonl",
            "".join(
                json.dumps(a, ensure_ascii=False, default=str) + "\n" for a in apartments
            ).encode(),
        )
    if media:
        atomic_bytes(
            outputs / "media.jsonl",
            "".join(json.dumps(m, ensure_ascii=False, default=str) + "\n" for m in media).encode(),
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect real Krasnoyarsk apartments and local photos"
    )
    parser.add_argument("--target", type=int, default=300)
    parser.add_argument("--max-photos", type=int, default=5)
    parser.add_argument("--max-pages", type=int, default=12)
    parser.add_argument("--max-per-building", type=int, default=3)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--allow-uneven",
        action="store_true",
        help="After district quotas, fill shortages from other districts",
    )
    parser.add_argument(
        "--restart", action="store_true", help="Rebuild selection from cached source pages"
    )
    args = parser.parse_args()
    if not 1 <= args.workers <= 8 or args.max_per_building < 1:
        parser.error("workers must be 1..8; max-per-building must be positive")
    if args.target < 1 or not 1 <= args.max_photos <= 20 or args.max_pages < 1 or args.delay < 0.5:
        parser.error("target/pages > 0, max-photos 1..20, delay >= 0.5s required")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    report = run(
        args.data_dir,
        args.target,
        args.max_photos,
        args.max_pages,
        args.offline,
        args.delay,
        args.max_per_building,
        args.workers,
        args.restart,
        args.allow_uneven,
    )
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in {"rejected", "network_or_media_errors"}},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
