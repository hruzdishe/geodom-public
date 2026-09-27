"""Local address enrichment; proximity is a location hint, never a verified POI address."""

import argparse
import hashlib
import json
import logging
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq
from pyproj import Transformer
from shapely import LineString, Point, Polygon, STRtree
from shapely.ops import transform

from .config import Settings
from .normalize import extract_address
from .osm import CollectionError, check_payload
from .pipeline import collect, write_json

logger = logging.getLogger(__name__)
PROJECT = Transformer.from_crs("EPSG:4326", "EPSG:32646", always_xy=True)
ROAD_TYPES = {
    "residential",
    "living_street",
    "tertiary",
    "secondary",
    "primary",
    "unclassified",
    "pedestrian",
    "service",
    "trunk",
}


def reference_bbox(table: pa.Table, buffer_m: float) -> tuple[float, float, float, float]:
    """Envelope of known city POIs, expanded in metric CRS to cover edge neighbours."""
    xs, ys = PROJECT.transform(table["lon"].to_pylist(), table["lat"].to_pylist())
    corners = [
        PROJECT.transform(x, y, direction="INVERSE")
        for x in (min(xs) - buffer_m, max(xs) + buffer_m)
        for y in (min(ys) - buffer_m, max(ys) + buffer_m)
    ]
    return (
        min(lat for lon, lat in corners),
        min(lon for lon, lat in corners),
        max(lat for lon, lat in corners),
        max(lon for lon, lat in corners),
    )


def address_query(timeout: int, bbox: tuple[float, float, float, float] | None = None) -> str:
    scope = "area.city" if bbox is None else ",".join(f"{v:.7f}" for v in bbox)
    return (
        f"[out:json][timeout:{timeout}];"
        "rel[place=city][wikidata=Q919]->.boundary;"
        ".boundary out tags;.boundary map_to_area->.city;"
        f'(node({scope})["addr:housenumber"];way({scope})["addr:housenumber"];'
        f'node({scope})["addr:full"];way({scope})["addr:full"];'
        f'way({scope})[highway~"^({"|".join(sorted(ROAD_TYPES))})$"][name];);'
        "out meta geom;"
    )


def element_geometry(element: dict):
    if element["type"] == "node":
        lon, lat = float(element["lon"]), float(element["lat"])
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError("Invalid coordinates")
        return transform(PROJECT.transform, Point(lon, lat))
    coordinates = [(p["lon"], p["lat"]) for p in element["geometry"]]
    if not all(-180 <= x <= 180 and -90 <= y <= 90 for x, y in coordinates):
        raise ValueError("Invalid coordinates")
    tags = element.get("tags", {})
    closed = len(coordinates) >= 4 and coordinates[0] == coordinates[-1]
    geom = (
        Polygon(coordinates)
        if closed and tags.get("building") not in {None, "no"}
        else LineString(coordinates)
    )
    if geom.is_empty or not geom.is_valid:
        raise ValueError("Invalid or empty geometry")
    return transform(PROJECT.transform, geom)


def build_indexes(payload: dict) -> tuple[list, list, dict]:
    addresses, roads, issues = [], [], []
    seen = set()
    for element in check_payload(payload):
        tags = element.get("tags", {})
        if tags.get("place") == "city" and tags.get("wikidata") == "Q919":
            continue
        identity = f"{element.get('type')}/{element.get('id')}"
        if identity in seen:
            continue
        seen.add(identity)
        address = extract_address(tags)
        usable_address = bool(tags.get("addr:full", "").strip()) or (
            bool(tags.get("addr:housenumber", "").strip())
            and bool((tags.get("addr:street") or tags.get("addr:place") or "").strip())
        )
        is_road = tags.get("highway") in ROAD_TYPES and tags.get("name")
        if not usable_address and not is_road:
            issues.append({"id": identity, "reason": "No usable house address or named street"})
            continue
        try:
            geometry = element_geometry(element)
        except (KeyError, ValueError, TypeError) as exc:
            issues.append({"id": identity, "reason": str(exc)})
            continue
        item = {"geometry": geometry, "id": identity, "updated_at": element.get("timestamp")}
        if usable_address:
            addresses.append(item | {"label": address})
        if is_road:
            roads.append(item | {"label": tags["name"]})
    return (
        addresses,
        roads,
        {
            "reference_issues": issues,
            "address_objects": len(addresses),
            "named_streets": len(roads),
        },
    )


def closest(point, items: list, tree: STRtree, max_distance: float):
    indices, distances = tree.query_nearest(point, max_distance=max_distance, return_distance=True)
    if not len(indices):
        return None
    # Deterministic tie handling for equal-distance objects.
    return min(
        ((items[int(i)], float(d)) for i, d in zip(indices, distances)),
        key=lambda pair: (pair[1], pair[0]["id"]),
    )


def enrich(
    table: pa.Table, payload: dict, max_address_m: float = 75, max_street_m: float = 150
) -> tuple[pa.Table, dict]:
    if max_address_m <= 0 or max_street_m <= 0:
        raise ValueError("Distance limits must be positive")
    addresses, roads, report = build_indexes(payload)
    address_tree = STRtree([a["geometry"] for a in addresses])
    by_identity = {a["id"]: a for a in addresses}
    road_tree = STRtree([r["geometry"] for r in roads])
    rows, methods = [], Counter()
    for row in table.to_pylist():
        original = extract_address(json.loads(row["tags"]))
        row.update(
            address=original,
            address_original=original,
            address_method="osm_tags" if original else "missing",
            address_source_id=row["source_id"] if original else None,
            address_distance_m=0.0 if original else None,
            address_is_approximate=False if original else None,
            address_source_updated_at=(
                row["source_updated_at"].isoformat()
                if original and row["source_updated_at"]
                else None
            ),
        )
        if not original:
            point = Point(*PROJECT.transform(row["lon"], row["lat"]))
            contained = [
                addresses[int(i)]
                for i in address_tree.query(point)
                if addresses[int(i)]["geometry"].geom_type == "Polygon"
                and addresses[int(i)]["geometry"].covers(point)
            ]
            # A bbox center can fall inside an unrelated building: never infer containment from it.
            verified_container = row["geometry_kind"] == "osm_node" and contained
            match = None
            if row["source_id"] in by_identity:
                match = (by_identity[row["source_id"]], 0.0)
                method = "osm_reference_tags"
            elif verified_container and len({a["label"] for a in contained}) == 1:
                match = (min(contained, key=lambda a: a["id"]), 0.0)
                method = "containing_building"
            else:
                match = closest(point, addresses, address_tree, max_address_m)
                method = "nearby_address"
                if match is None:
                    match = closest(point, roads, road_tree, max_street_m)
                    method = "nearby_street"
            if match:
                item, distance = match
                approximate = method not in {"containing_building", "osm_reference_tags"}
                row.update(
                    address=("Рядом с: " if approximate else "") + item["label"],
                    address_method=method,
                    address_source_id=item["id"],
                    address_distance_m=round(distance, 2),
                    address_is_approximate=approximate,
                    address_source_updated_at=item["updated_at"],
                )
        # Every POI can be shown honestly on the map, including forests without postal addresses.
        row["location_label"] = (
            row["address"] or f"Красноярск, координаты {row['lat']:.6f}, {row['lon']:.6f}"
        )
        methods[row["address_method"]] += 1
        rows.append(row)
    fields = {
        "address_original": pa.string(),
        "address_method": pa.string(),
        "address_source_id": pa.string(),
        "address_distance_m": pa.float64(),
        "address_is_approximate": pa.bool_(),
        "address_source_updated_at": pa.string(),
        "location_label": pa.string(),
    }
    schema = table.schema
    for name, dtype in fields.items():
        if name not in schema.names:
            schema = schema.append(pa.field(name, dtype))
    report.update(
        rows=len(rows),
        methods=dict(methods),
        max_address_m=max_address_m,
        max_street_m=max_street_m,
        metric_crs="EPSG:32646",
        warnings=[
            "Nearby addresses/streets are location hints, not verified postal addresses.",
            "Buildings represented as OSM relations are not used in this version.",
            "POI bbox centers are approximate locations; no containment inferred for them.",
        ],
    )
    return pa.Table.from_pylist(rows, schema=schema), report


def enrich_file(settings: Settings, raw: Path, max_address_m: float, max_street_m: float) -> dict:
    content = raw.read_bytes()
    metadata = json.loads(raw.with_suffix(".metadata.json").read_text(encoding="utf-8"))
    if hashlib.sha256(content).hexdigest() != metadata["sha256"]:
        raise CollectionError("Address raw checksum mismatch")
    target = settings.data_dir / "processed/geo_objects.parquet"
    table, report = enrich(pq.read_table(target), json.loads(content), max_address_m, max_street_m)
    report.update(raw_path=str(raw), raw_metadata=metadata)
    temp = target.with_name(f".{uuid4().hex}.parquet")
    try:
        pq.write_table(table, temp, compression="zstd")
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)
    write_json(settings.data_dir / "processed/address_enrichment_report.json", report)
    dataset_meta = target.with_suffix(".metadata.json")
    if dataset_meta.exists():
        provenance = json.loads(dataset_meta.read_text(encoding="utf-8"))
        provenance["address_enrichment"] = {
            "raw_path": str(raw),
            "raw_sha256": metadata["sha256"],
            "collected_at": metadata["collected_at"],
            "timestamp_osm_base": metadata.get("timestamp_osm_base"),
            "methods": report["methods"],
            "max_address_m": max_address_m,
            "max_street_m": max_street_m,
        }
        write_json(dataset_meta, provenance)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect address reference / enrich POIs locally")
    parser.add_argument("stage", choices=["collect", "enrich", "run"])
    parser.add_argument("--raw", type=Path)
    parser.add_argument("--max-address-m", type=float)
    parser.add_argument("--max-street-m", type=float)
    args = parser.parse_args()
    if args.stage == "enrich" and args.raw is None:
        parser.error("enrich requires --raw")
    settings = Settings()
    max_address_m = args.max_address_m if args.max_address_m is not None else settings.max_address_m
    max_street_m = args.max_street_m if args.max_street_m is not None else settings.max_street_m
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "source": "openstreetmap",
        "stage": args.stage,
        "errors": [],
    }
    result = 0
    try:
        bbox = None
        if args.stage != "enrich":
            pois = pq.read_table(settings.data_dir / "processed/geo_objects.parquet")
            bbox = reference_bbox(pois, max(max_address_m, max_street_m))
        raw = (
            collect(settings, address_query(settings.query_timeout_seconds, bbox), "osm_addresses")
            if args.stage != "enrich"
            else args.raw
        )
        if args.stage != "collect":
            report.update(enrich_file(settings, raw, max_address_m, max_street_m))
        print(
            json.dumps(
                {k: v for k, v in report.items() if k != "reference_issues"},
                ensure_ascii=False,
                indent=2,
            )
        )
    except Exception as exc:
        logger.exception("Address pipeline failed")
        report["errors"].append(str(exc))
        result = 1
    finally:
        report["finished_at"] = datetime.now(UTC).isoformat()
        write_json(settings.data_dir / "reports" / f"addresses-{uuid4().hex}.json", report)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
