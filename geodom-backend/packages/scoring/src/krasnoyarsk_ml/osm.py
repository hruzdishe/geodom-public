"""One city-wide query; no per-apartment requests or inferred polygon geometry."""

import logging
import time
from typing import Any

import httpx

from .config import Settings

logger = logging.getLogger(__name__)

# Ordered precedence gives one record per OSM identity, even with multiple matching tags.
TAXONOMY = {
    "amenity": {
        "school": "education",
        "kindergarten": "education",
        "college": "education",
        "university": "education",
        "hospital": "health",
        "clinic": "health",
        "pharmacy": "health",
    },
    "healthcare": {"hospital": "health", "clinic": "health", "pharmacy": "health"},
    "leisure": {
        "park": "green",
        "playground": "green",
        "sports_centre": "sport",
        "fitness_centre": "sport",
    },
    "landuse": {"forest": "green"},
    "natural": {"wood": "green"},
    "shop": {"supermarket": "shopping", "mall": "shopping"},
    "highway": {"bus_stop": "transport"},
    "railway": {"tram_stop": "transport", "station": "transport"},
}


class CollectionError(RuntimeError):
    pass


def build_query(timeout: int) -> str:
    # Wikidata Q919 identifies Krasnoyarsk, avoiding ambiguous names and guessed relation IDs.
    selectors = "\n".join(
        f'nwr(area.city)["{key}"~"^({"|".join(values)})$"];' for key, values in TAXONOMY.items()
    )
    return (
        f"[out:json][timeout:{timeout}];\n"
        'rel["place"="city"]["wikidata"="Q919"]->.boundary;\n'
        ".boundary out tags;\n.boundary map_to_area ->.city;\n"
        f"({selectors});\nout meta center;\n"
    )


def check_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("remark"):
        raise CollectionError(f"Overpass returned incomplete data: {payload['remark']}")
    elements = payload.get("elements")
    if not isinstance(elements, list):
        raise CollectionError("Missing elements array")
    boundaries = [
        e
        for e in elements
        if e.get("type") == "relation"
        and e.get("tags", {}).get("wikidata") == "Q919"
        and e.get("tags", {}).get("place") == "city"
    ]
    if len(boundaries) != 1:
        raise CollectionError(f"Expected one Krasnoyarsk boundary, got {len(boundaries)}")
    if len(elements) <= 1:
        raise CollectionError("City query returned no POIs; check Overpass area availability")
    return elements


def fetch(settings: Settings, query: str) -> bytes:
    """Retry transient HTTP/network errors; semantic validation happens after raw persistence."""
    with httpx.Client(
        timeout=settings.timeout_seconds,
        headers={
            "User-Agent": "krasnoyarsk-ml/0.1 (OSM research collector)",
        },
    ) as client:
        for attempt in range(settings.attempts):
            try:
                response = client.get(str(settings.overpass_url), params={"data": query})
                response.raise_for_status()
                return response.content
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in {
                    408,
                    429,
                    500,
                    502,
                    503,
                    504,
                }:
                    raise CollectionError(f"Overpass HTTP {exc.response.status_code}") from exc
                if attempt + 1 == settings.attempts:
                    raise CollectionError(
                        f"Overpass failed after {settings.attempts} attempts"
                    ) from exc
                delay = min(settings.backoff_seconds * 2**attempt, 60)
                logger.warning("Overpass attempt %s failed; retry in %ss", attempt + 1, delay)
                time.sleep(delay)
    raise CollectionError("No request attempted")
