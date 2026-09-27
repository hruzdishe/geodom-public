"""Offline infrastructure features: WGS84 geodesic distances between source points."""

import argparse
import hashlib
import json
import math
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq
from pyproj import Geod

from .pipeline import atomic_bytes, write_json

VERSION = "infrastructure_v1"
METHOD = "wgs84_geodesic_between_representative_points"
GEOD = Geod(ellps="WGS84")
LABELS = {
    "school": "Школы",
    "kindergarten": "Детские сады",
    "hospital": "Больницы",
    "clinic": "Клиники и поликлиники",
    "pharmacy": "Аптеки",
    "bus_stop": "Автобусные остановки",
    "tram_stop": "Трамвайные остановки",
    "station": "Железнодорожные станции",
    "park": "Парки",
    "forest": "Леса",
    "playground": "Детские площадки",
    "supermarket": "Супермаркеты",
    "mall": "Торговые центры",
    "sports_centre": "Спортивные центры",
    "fitness_centre": "Фитнес-центры",
    "college": "Колледжи",
    "university": "Университеты",
    "public_transport": "Автобусные и трамвайные остановки",
}
GROUPS = {key: (key,) for key in LABELS if key != "public_transport"}
GROUPS["public_transport"] = ("bus_stop", "tram_stop")
WARNINGS = [
    "OSM completeness is not verified: zero counts do not prove real-world absence.",
    "City-only extraction may omit objects outside the city, including near-border neighbours.",
    "Distances use source representative points, not entrances, polygon boundaries or routes.",
    "Distinct OSM IDs may describe one facility; counts are OSM objects, not unique institutions.",
    "Address enrichment does not refresh POI coordinates or the original OSM snapshot date.",
]


def validated_rows(table: pa.Table, kind: str) -> list[dict]:
    required = {"id", "lat", "lon"}
    if kind == "pois":
        required |= {"subcategory", "geometry_kind"}
    if missing := required - set(table.column_names):
        raise ValueError(f"{kind}: missing columns {sorted(missing)}")
    rows, seen = table.to_pylist(), set()
    for row in rows:
        identifier = row["id"]
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise ValueError(f"{kind}: empty or duplicate ID {identifier!r}")
        seen.add(identifier)
        for field, limit in (("lat", 90), ("lon", 180)):
            value = row[field]
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(value)
                or not -limit <= value <= limit
            ):
                raise ValueError(f"{kind}: invalid {field} for {identifier}")
        if kind == "pois":
            if row["subcategory"] not in set().union(*map(set, GROUPS.values())):
                raise ValueError(f"Unknown POI subcategory: {row['subcategory']}")
            if row["geometry_kind"] not in {"osm_node", "bbox_center"}:
                raise ValueError(f"Unknown POI geometry kind: {row['geometry_kind']}")
    return sorted(rows, key=lambda r: r["id"])


def schemas() -> tuple[pa.Schema, pa.Schema]:
    fields = [
        ("apartment_id", pa.string()),
        ("feature_version", pa.string()),
        ("computed_at", pa.timestamp("us", tz="UTC")),
        ("poi_snapshot_at", pa.timestamp("us", tz="UTC")),
        ("poi_coverage_verified", pa.bool_()),
        ("distance_method", pa.string()),
    ]
    for group in GROUPS:
        fields.extend(
            [
                (f"{group}_nearest_distance_m", pa.float64()),
                (f"{group}_nearest_poi_id", pa.string()),
                (f"{group}_count_500m", pa.int64()),
                (f"{group}_count_1000m", pa.int64()),
                (f"{group}_observed_in_snapshot", pa.bool_()),
            ]
        )
    nearest = [
        ("apartment_id", pa.string()),
        ("feature_group", pa.string()),
        ("poi_id", pa.string()),
        ("distance_m", pa.float64()),
        ("poi_name", pa.string()),
        ("poi_subcategory", pa.string()),
        ("poi_lat", pa.float64()),
        ("poi_lon", pa.float64()),
        ("poi_geometry_kind", pa.string()),
        ("poi_is_bbox_center", pa.bool_()),
        ("poi_address", pa.string()),
        ("poi_address_method", pa.string()),
        ("poi_address_is_approximate", pa.bool_()),
        ("poi_source_url", pa.string()),
        ("apartment_coordinate_method", pa.string()),
        ("poi_snapshot_at", pa.timestamp("us", tz="UTC")),
    ]
    metadata = {
        b"feature_version": VERSION.encode(),
        b"distance_method": METHOD.encode(),
        b"distance_unit": b"metre",
        b"count_unit": b"distinct OSM identity",
        b"attribution": b"OpenStreetMap contributors; ODbL 1.0",
    }
    return pa.schema(fields, metadata=metadata), pa.schema(nearest, metadata=metadata)


def calculate(
    apartments: pa.Table,
    pois: pa.Table,
    *,
    snapshot_at: datetime | None = None,
    computed_at: datetime | None = None,
) -> tuple[pa.Table, pa.Table, dict]:
    homes, objects = validated_rows(apartments, "apartments"), validated_rows(pois, "pois")
    if not homes:
        raise ValueError("No apartments to compute")
    now = computed_at or datetime.now(UTC)
    for stamp in (now, snapshot_at):
        if stamp is not None and (stamp.tzinfo is None or stamp.utcoffset() is None):
            raise ValueError("Timestamps must include timezone")
    if snapshot_at is not None and snapshot_at > now:
        raise ValueError("POI snapshot is later than computation time")
    indexes = {
        group: [i for i, p in enumerate(objects) if p["subcategory"] in subcategories]
        for group, subcategories in GROUPS.items()
    }
    results, links = [], []
    for home in homes:
        # One vectorized geodesic calculation; the overlapping transport group reuses it.
        distances = (
            GEOD.inv(
                [home["lon"]] * len(objects),
                [home["lat"]] * len(objects),
                [p["lon"] for p in objects],
                [p["lat"] for p in objects],
            )[2]
            if objects
            else []
        )
        if not all(math.isfinite(d) and d >= 0 for d in distances):
            raise ValueError(f"Invalid computed distance for {home['id']}")
        row = {
            "apartment_id": home["id"],
            "feature_version": VERSION,
            "computed_at": now,
            "poi_snapshot_at": snapshot_at,
            "poi_coverage_verified": False,
            "distance_method": METHOD,
        }
        for group, candidates in indexes.items():
            # Stable tie-break by source ID, independent of input file row order.
            nearest_index = (
                min(candidates, key=lambda i: (distances[i], objects[i]["id"]))
                if candidates
                else None
            )
            point = objects[nearest_index] if nearest_index is not None else {}
            distance = round(distances[nearest_index], 3) if nearest_index is not None else None
            row.update(
                {
                    f"{group}_nearest_distance_m": distance,
                    f"{group}_nearest_poi_id": point.get("id"),
                    f"{group}_observed_in_snapshot": bool(candidates),
                }
            )
            for radius in (500, 1000):
                # Inclusive radii; numerical tolerance is one micrometre, not display rounding.
                row[f"{group}_count_{radius}m"] = sum(
                    distances[i] <= radius + 1e-6 for i in candidates
                )
            links.append(
                {
                    "apartment_id": home["id"],
                    "feature_group": group,
                    "poi_id": point.get("id"),
                    "distance_m": distance,
                    "poi_name": point.get("name"),
                    "poi_subcategory": point.get("subcategory"),
                    "poi_lat": point.get("lat"),
                    "poi_lon": point.get("lon"),
                    "poi_geometry_kind": point.get("geometry_kind"),
                    "poi_is_bbox_center": point.get("geometry_kind") == "bbox_center"
                    if point
                    else None,
                    "poi_address": point.get("address"),
                    "poi_address_method": point.get("address_method"),
                    "poi_address_is_approximate": point.get("address_is_approximate"),
                    "poi_source_url": point.get("source_url"),
                    "apartment_coordinate_method": home.get("coordinate_method"),
                    "poi_snapshot_at": snapshot_at,
                }
            )
        results.append(row)
    wide_schema, links_schema = schemas()
    summary = {}
    for group, candidates in indexes.items():
        distances = [
            r[f"{group}_nearest_distance_m"]
            for r in results
            if r[f"{group}_nearest_distance_m"] is not None
        ]
        summary[group] = {
            "label": LABELS[group],
            "source_objects": len(candidates),
            "apartments_within_500m": sum(r[f"{group}_count_500m"] > 0 for r in results),
            "apartments_within_1000m": sum(r[f"{group}_count_1000m"] > 0 for r in results),
            "nearest_distance_min_m": min(distances) if distances else None,
            "nearest_distance_median_m": round(median(distances), 3) if distances else None,
            "nearest_distance_max_m": max(distances) if distances else None,
        }
    report = {
        "feature_version": VERSION,
        "computed_at": now.isoformat(),
        "apartments": len(homes),
        "poi_objects": len(objects),
        "feature_groups": len(GROUPS),
        "nearest_rows": len(links),
        "distance_method": METHOD,
        "poi_snapshot_at": snapshot_at.isoformat() if snapshot_at else None,
        "poi_snapshot_age_days": round((now - snapshot_at).total_seconds() / 86400, 2)
        if snapshot_at
        else None,
        "poi_geometry_counts": dict(Counter(p["geometry_kind"] for p in objects)),
        "groups": summary,
        "warnings": list(WARNINGS),
    }
    if snapshot_at is None:
        report["warnings"].append("POI snapshot date is unknown.")
    elif (now - snapshot_at).days > 7:
        report["warnings"].append(f"POI snapshot is {(now - snapshot_at).days} days old.")
    if not objects:
        report["warnings"].append("No POIs supplied: all groups are unobserved.")
    return (
        pa.Table.from_pylist(results, schema=wide_schema),
        pa.Table.from_pylist(links, schema=links_schema),
        report,
    )


def write_table(path: Path, table: pa.Table) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{uuid4().hex}.parquet")
    try:
        pq.write_table(table, temp, compression="zstd")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def run(apartments_path: Path, pois_path: Path, metadata_path: Path, output: Path) -> dict:
    metadata = (
        json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    )
    snapshot = metadata.get("timestamp_osm_base")
    wide, nearest, report = calculate(
        pq.read_table(apartments_path),
        pq.read_table(pois_path),
        snapshot_at=datetime.fromisoformat(snapshot) if snapshot else None,
    )
    report["inputs"] = {
        name: {"filename": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for name, path in (
            ("apartments", apartments_path),
            ("pois", pois_path),
            ("poi_metadata", metadata_path),
        )
        if path.exists()
    }
    report["osm_provenance"] = {
        key: metadata.get(key)
        for key in ("source", "license", "attribution", "collected_at", "timestamp_osm_base")
    }
    outputs = {}
    for name, table in (("apartment_features", wide), ("apartment_nearest_pois", nearest)):
        parquet = output / f"{name}.parquet"
        write_table(parquet, table)
        if not pq.read_table(parquet).equals(table):
            raise ValueError(f"Parquet round-trip mismatch: {name}")
        jsonl = output / f"{name}.jsonl"
        atomic_bytes(
            jsonl,
            "".join(
                json.dumps(r, ensure_ascii=False, default=lambda d: d.isoformat()) + "\n"
                for r in table.to_pylist()
            ).encode("utf-8"),
        )
        for path in (parquet, jsonl):
            outputs[path.name] = {
                "rows": table.num_rows,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
    report["outputs"] = outputs
    report["status"] = "complete"
    write_json(output / "feature_report.json", report)
    write_json(
        output / "feature_catalog.json",
        {
            "version": VERSION,
            "join": "apartment_features.apartment_id = apartments.id",
            "poi_join": "apartment_nearest_pois.poi_id = geo_objects.id",
            "radii_m": [500, 1000],
            "distance_method": METHOD,
            "groups": {
                g: {"label": LABELS[g], "subcategories": list(v)} for g, v in GROUPS.items()
            },
            "semantics": {
                "nearest_distance_m": "Metres to nearest representative point in the entire supplied snapshot; null if group absent.",
                "nearest_poi_id": "OSM ID of selected nearest point; null if group absent.",
                "count_500m/count_1000m": "Distinct OSM identities within inclusive radius, not unique institutions; 0 is not verified real-world absence.",
                "observed_in_snapshot": "At least one object of this group exists somewhere in the supplied snapshot; not local coverage verification.",
                "poi_coverage_verified": "Always false in v1: completeness and city-border buffer coverage are unverified.",
            },
            "columns": [{"name": f.name, "type": str(f.type)} for f in wide.schema],
        },
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute offline apartment infrastructure features"
    )
    parser.add_argument(
        "--apartments", type=Path, default=Path("data/processed/housing/apartments.parquet")
    )
    parser.add_argument("--pois", type=Path, default=Path("data/processed/geo_objects.parquet"))
    parser.add_argument(
        "--poi-metadata", type=Path, default=Path("data/processed/geo_objects.metadata.json")
    )
    parser.add_argument("--output", type=Path, default=Path("data/processed/features"))
    args = parser.parse_args()
    report = run(args.apartments, args.pois, args.poi_metadata, args.output)
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "status",
                    "apartments",
                    "poi_objects",
                    "feature_groups",
                    "nearest_rows",
                    "poi_snapshot_at",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
