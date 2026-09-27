import json
from collections import Counter
from datetime import datetime
from typing import Any, Literal

import pyarrow as pa
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError

from .osm import TAXONOMY, check_payload


class GeoObject(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    id: str
    osm_id: int = Field(gt=0)
    osm_type: Literal["node", "way", "relation"]
    category: str
    subcategory: str
    name: str | None
    address: str | None
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    geometry: str
    geometry_kind: Literal["osm_node", "bbox_center"]
    tags: str
    source: str = "openstreetmap"
    source_id: str
    source_url: str
    source_updated_at: AwareDatetime | None
    collected_at: AwareDatetime


SCHEMA = pa.schema(
    [
        ("id", pa.string()),
        ("osm_id", pa.int64()),
        ("osm_type", pa.string()),
        ("category", pa.string()),
        ("subcategory", pa.string()),
        ("name", pa.string()),
        ("address", pa.string()),
        ("lat", pa.float64()),
        ("lon", pa.float64()),
        ("geometry", pa.string()),
        ("geometry_kind", pa.string()),
        ("tags", pa.string()),
        ("source", pa.string()),
        ("source_id", pa.string()),
        ("source_url", pa.string()),
        ("source_updated_at", pa.timestamp("us", tz="UTC")),
        ("collected_at", pa.timestamp("us", tz="UTC")),
    ],
    metadata={
        b"crs": b"EPSG:4326",
        b"geometry_encoding": b"WKT Point; representative location only",
        b"attribution": b"OpenStreetMap contributors; ODbL 1.0",
    },
)


def extract_address(tags: dict[str, str]) -> str | None:
    """Use explicit OSM address tags only; partial addresses remain partial."""

    def value(key: str) -> str:
        return tags.get(f"addr:{key}", "").strip()

    if full := value("full"):
        return full
    street_house = " ".join(
        part for part in (value("street") or value("place"), value("housenumber")) if part
    )
    parts = [value("postcode"), value("city"), value("suburb"), street_house]
    if unit := value("unit"):
        parts.append(f"пом. {unit}")
    return ", ".join(part for part in parts if part) or None


def normalize(payload: dict[str, Any], collected_at: datetime) -> tuple[pa.Table, dict]:
    elements = check_payload(payload)
    rows: list[dict] = []
    issues: list[dict] = []
    seen: set[str] = set()
    skipped = duplicates = 0
    for element in elements:
        tags = element.get("tags", {})
        classification = next(
            (
                (values[tags[key]], "forest" if tags[key] == "wood" else tags[key])
                for key, values in TAXONOMY.items()
                if tags.get(key) in values
            ),
            None,
        )
        if classification is None:
            skipped += 1
            continue
        identity = f"{element.get('type')}/{element.get('id')}"
        if identity in seen:
            duplicates += 1
            issues.append({"id": identity, "reason": "duplicate OSM identity"})
            continue
        try:
            coords = element if element.get("type") == "node" else element.get("center", {})
            lat, lon = float(coords["lat"]), float(coords["lon"])
            row = GeoObject(
                id=f"osm:{identity}",
                osm_id=element["id"],
                osm_type=element["type"],
                category=classification[0],
                subcategory=classification[1],
                name=tags.get("name"),
                address=extract_address(tags),
                lat=lat,
                lon=lon,
                geometry=f"POINT ({lon} {lat})",
                geometry_kind="osm_node" if element["type"] == "node" else "bbox_center",
                tags=json.dumps(tags, ensure_ascii=False, sort_keys=True),
                source_id=identity,
                source_url=f"https://www.openstreetmap.org/{identity}",
                source_updated_at=element.get("timestamp"),
                collected_at=collected_at,
            )
            rows.append(row.model_dump())
            seen.add(identity)
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            issues.append({"id": identity, "reason": str(exc)})
    counts = Counter(row["subcategory"] for row in rows)
    return pa.Table.from_pylist(sorted(rows, key=lambda r: r["id"]), schema=SCHEMA), {
        "records_received": len(elements),
        "records_valid": len(rows),
        "records_with_address": sum(row["address"] is not None for row in rows),
        "records_invalid": len(issues) - duplicates,
        "records_duplicate": duplicates,
        "records_skipped": skipped,
        "issues": issues,
        "subcategory_counts": dict(counts),
        "warnings": [
            "OSM coverage is incomplete; zero objects does not prove absence.",
            "Ways/relations use bounding-box centers, not polygon geometries or entrances.",
            "Distinct OSM identities may describe the same facility; no fuzzy deduplication.",
        ],
    }
