"""Versioned OSM polygons and residential-area-weighted district reference points."""

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon, box, mapping, shape
from shapely.ops import polygonize_full, transform, unary_union

from .config import Settings
from .housing.sibdom import DISTRICTS
from .osm import CollectionError, fetch
from .pipeline import atomic_bytes, write_json

METRIC_CRS = "EPSG:32646"
TO_METRIC = Transformer.from_crs("EPSG:4326", METRIC_CRS, always_xy=True).transform
TO_WGS84 = Transformer.from_crs(METRIC_CRS, "EPSG:4326", always_xy=True).transform
RESIDENTIAL_BUILDINGS = {
    "apartments",
    "residential",
    "house",
    "detached",
    "semidetached_house",
    "terrace",
    "dormitory",
    "bungalow",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect_geometry(directory: Path, settings: Settings) -> dict:
    """Download only on explicit collection; preserve each response and its query."""
    prefix = (
        '[out:json][timeout:180];rel["place"="city"]["wikidata"="Q919"]->.city;'
        ".city map_to_area->.a;"
    )
    queries = {
        "boundaries": prefix
        + 'rel(area.a)["boundary"="administrative"]["admin_level"="9"];out meta geom;',
        "residential": prefix + '(way(area.a)["landuse"="residential"];'
        'rel(area.a)["landuse"="residential"];);out meta geom;',
    }
    report = {}
    for name, query in queries.items():
        content = fetch(settings, query)
        payload = json.loads(content)
        digest = hashlib.sha256(content).hexdigest()
        archive = directory / "archive" / f"{name}_{digest}.json"
        atomic_bytes(archive, content)
        if payload.get("remark") or not payload.get("elements"):
            raise CollectionError(f"Incomplete {name}: {payload.get('remark', 'no elements')}")
        metadata = {
            "source_url": str(settings.overpass_url),
            "query": query,
            "retrieved_at": datetime.now(UTC).isoformat(),
            "sha256": digest,
            "snapshot_at": payload.get("osm3s", {}).get("timestamp_osm_base"),
            "license": "ODbL-1.0",
            "attribution": "OpenStreetMap contributors",
        }
        write_json(archive.with_suffix(".metadata.json"), metadata)
        atomic_bytes(directory / f"{name}.json", content)
        write_json(directory / f"{name}.metadata.json", metadata)
        report[name] = metadata
    return report


def osm_polygon(element: dict):
    """Assemble complete member rings, respecting holes; never close broken boundaries."""
    if element["type"] == "way":
        coordinates = [(p["lon"], p["lat"]) for p in element.get("geometry", [])]
        if len(coordinates) < 4 or coordinates[0] != coordinates[-1]:
            raise ValueError("Unclosed or missing way geometry")
        result = Polygon(coordinates)
    elif element["type"] == "relation":
        rings = {}
        for role in ("outer", "inner"):
            lines = []
            for member in element.get("members", []):
                if member.get("role") != role:
                    continue
                if member.get("type") != "way" or not member.get("geometry"):
                    raise ValueError("Incomplete/nested polygon member")
                lines.append(LineString([(p["lon"], p["lat"]) for p in member["geometry"]]))
            polygons, cuts, dangles, invalid = polygonize_full(lines)
            if not cuts.is_empty or not dangles.is_empty or not invalid.is_empty:
                raise ValueError("Disconnected polygon members")
            rings[role] = unary_union(list(polygons.geoms))
        result = rings["outer"].difference(rings["inner"])
    else:
        raise ValueError("Not a polygon element")
    if (
        result.is_empty
        or not result.is_valid
        or result.geom_type not in {"Polygon", "MultiPolygon"}
    ):
        raise ValueError("Empty or invalid polygon")
    if not all(math.isfinite(v) for v in result.bounds):
        raise ValueError("Non-finite polygon coordinates")
    return result


def district_polygons(payload: dict) -> dict:
    if payload.get("remark"):
        raise ValueError("Partial Overpass response")
    features, seen = [], set()
    names = {v: k for k, v in DISTRICTS.items()}
    snapshot = payload.get("osm3s", {}).get("timestamp_osm_base")
    for element in payload["elements"]:
        tags = element.get("tags", {})
        name = tags.get("name", "").removesuffix(" район")
        if name not in names or tags.get("boundary") != "administrative":
            continue
        if name in seen:
            raise ValueError(f"Ambiguous boundary: {name}")
        seen.add(name)
        geometry = osm_polygon(element)
        features.append(
            {
                "type": "Feature",
                "geometry": mapping(geometry),
                "properties": {
                    "district_id": f"osm:relation:{element['id']}",
                    "district_name": name,
                    "listing_district_id": names[name],
                    "osm_version": element.get("version"),
                    "source_url": f"https://www.openstreetmap.org/relation/{element['id']}",
                    "boundary_version": f"osm:{snapshot}:v{element.get('version', 'unknown')}",
                    "boundary_snapshot_at": snapshot,
                    "official_boundary_verified": False,
                },
            }
        )
    if seen != set(names):
        raise ValueError(f"Expected seven districts; missing {sorted(set(names) - seen)}")
    projected = [transform(TO_METRIC, shape(f["geometry"])) for f in features]
    for i, left in enumerate(projected):
        for right in projected[i + 1 :]:
            if left.intersection(right).area > 1:
                raise ValueError("District boundaries overlap by more than 1 square metre")
    return {
        "type": "FeatureCollection",
        "features": sorted(features, key=lambda f: f["properties"]["district_id"]),
    }


def residential_mask(payload: dict, buildings_payload: dict | None = None) -> tuple:
    if payload.get("remark") or (buildings_payload or {}).get("remark"):
        raise ValueError("Partial residential geometry response")
    polygons, errors = [], []
    counts = {"landuse": 0, "buildings": 0}
    for kind, items in (
        ("landuse", payload.get("elements", [])),
        ("buildings", (buildings_payload or {}).get("elements", [])),
    ):
        for element in items:
            tags = element.get("tags", {})
            accepted = (
                tags.get("landuse") == "residential"
                if kind == "landuse"
                else (tags.get("building") in RESIDENTIAL_BUILDINGS)
            )
            if not accepted:
                continue
            try:
                polygons.append(transform(TO_METRIC, osm_polygon(element)))
                counts[kind] += 1
            except ValueError as exc:
                errors.append(
                    {"osm_id": element["id"], "type": element["type"], "reason": str(exc)}
                )
    if not polygons:
        raise ValueError("No valid residential polygons")
    return unary_union(polygons), {"accepted": counts, "rejected": errors}


def build_grid(geojson: dict, residential, cell_size: int = 250) -> tuple[list, list]:
    if isinstance(cell_size, bool) or not isinstance(cell_size, int) or not 50 <= cell_size <= 1000:
        raise ValueError("cell_size must be an integer in 50..1000 metres")
    points, summary = [], []
    for feature in geojson["features"]:
        props = feature["properties"]
        district = transform(TO_METRIC, shape(feature["geometry"]))
        area = district.intersection(residential)
        if area.is_empty:
            raise ValueError(f"No residential coverage: {props['district_name']}")
        xmin, ymin, xmax, ymax = area.bounds
        start = len(points)
        for x in range(math.floor(xmin / cell_size), math.ceil(xmax / cell_size)):
            for y in range(math.floor(ymin / cell_size), math.ceil(ymax / cell_size)):
                piece = area.intersection(
                    box(x * cell_size, y * cell_size, (x + 1) * cell_size, (y + 1) * cell_size)
                )
                if piece.area <= 0:
                    continue
                # Disconnected pieces get independent representative points and exact area weights.
                parts = (
                    list(piece.geoms)
                    if piece.geom_type in {"MultiPolygon", "GeometryCollection"}
                    else [piece]
                )
                parts = sorted((p for p in parts if p.area > 0), key=lambda p: (*p.bounds, p.area))
                for index, part in enumerate(parts):
                    point = transform(TO_WGS84, part.representative_point())
                    points.append(
                        {
                            "id": f"{props['district_id']}:{x}:{y}:{index}",
                            "district_id": props["district_id"],
                            "district_name": props["district_name"],
                            "lat": point.y,
                            "lon": point.x,
                            "weight_m2": part.area,
                            "cell_x": x,
                            "cell_y": y,
                            "cell_size_m": cell_size,
                            "weight_method": "mapped_residential_area_not_population",
                            "coordinate_method": "residential_intersection_representative_point",
                        }
                    )
        summary.append(
            props
            | {
                "area_km2": district.area / 1e6,
                "mapped_residential_area_km2": area.area / 1e6,
                "reference_points": len(points) - start,
                "residential_coverage_verified": False,
            }
        )
    return points, summary


def audit_apartments(apartments: list[dict], geojson: dict, residential) -> list[dict]:
    polygons = [(f["properties"], shape(f["geometry"])) for f in geojson["features"]]
    result = []
    for home in apartments:
        if any(
            not isinstance(home.get(k), (int, float)) or not math.isfinite(home[k])
            for k in ("lon", "lat")
        ):
            matches, point = [], None
        else:
            point = Point(home["lon"], home["lat"])
            matches = [p for p, geom in polygons if geom.covers(point)]
        assigned = matches[0] if len(matches) == 1 else None
        result.append(
            {
                "apartment_id": home["id"],
                "listing_district_name": home.get("district_name"),
                "spatial_district_id": assigned["district_id"] if assigned else None,
                "spatial_district_name": assigned["district_name"] if assigned else None,
                "status": "ambiguous_boundary"
                if len(matches) > 1
                else "outside_boundaries"
                if not assigned
                else "match"
                if assigned["district_name"] == home.get("district_name")
                else "listing_geometry_mismatch",
                "inside_mapped_residential_area": residential.covers(transform(TO_METRIC, point))
                if point is not None
                else None,
            }
        )
    return result


def write_parquet(path: Path, rows: list[dict]) -> None:
    table = pa.Table.from_pylist(rows)
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink, compression="zstd")
    atomic_bytes(path, sink.getvalue().to_pybytes())
