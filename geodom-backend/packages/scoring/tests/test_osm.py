import hashlib
import json
from datetime import UTC, datetime

import httpx
import pyarrow.parquet as pq
import pytest

from krasnoyarsk_ml.config import Settings
from krasnoyarsk_ml.normalize import normalize
from krasnoyarsk_ml.osm import CollectionError, build_query, check_payload, fetch
from krasnoyarsk_ml.pipeline import collect, preprocess, write_json

NOW = datetime(2026, 9, 26, tzinfo=UTC)


def fixture_payload():
    # Synthetic test fixtures only, never used as product data.
    return {
        "elements": [
            {
                "type": "relation",
                "id": 1,
                "tags": {"place": "city", "wikidata": "Q919"},
            },
            {
                "type": "node",
                "id": 2,
                "lat": 56.01,
                "lon": 92.87,
                "timestamp": "2025-01-01T00:00:00Z",
                "tags": {"amenity": "school"},
            },
            {
                "type": "way",
                "id": 2,
                "center": {"lat": 56.02, "lon": 92.88},
                "tags": {"leisure": "park"},
            },
        ]
    }


def test_normalization_identity_geometry_and_provenance():
    table, report = normalize(fixture_payload(), NOW)
    rows = table.to_pylist()
    assert table.num_rows == 2
    assert rows[0]["id"] != rows[1]["id"]
    assert rows[0]["geometry"] == "POINT (92.87 56.01)"
    assert rows[1]["geometry_kind"] == "bbox_center"
    assert rows[0]["source_updated_at"].year == 2025
    assert rows[1]["source_updated_at"] is None
    assert report["records_invalid"] == 0


@pytest.mark.parametrize(
    "tags,expected",
    [
        ({"addr:full": " Готовый адрес ", "addr:street": "Другая улица"}, "Готовый адрес"),
        (
            {"addr:city": "Красноярск", "addr:street": "улица Ленина", "addr:housenumber": "10А"},
            "Красноярск, улица Ленина 10А",
        ),
        ({"addr:place": "микрорайон Северный", "addr:housenumber": "5"}, "микрорайон Северный 5"),
        ({"addr:street": "улица Ленина"}, "улица Ленина"),
        ({"addr:full": "   "}, None),
    ],
)
def test_address_in_normalized_table(tags, expected):
    payload = fixture_payload()
    payload["elements"][1]["tags"].update(tags)
    table, report = normalize(payload, NOW)
    assert table["address"].to_pylist() == [expected, None]
    assert report["records_with_address"] == int(expected is not None)


def test_invalid_coordinates_missing_center_and_duplicates_reported():
    payload = fixture_payload()
    payload["elements"] += [
        payload["elements"][1],
        {"type": "node", "id": 3, "lat": float("nan"), "lon": 92, "tags": {"amenity": "school"}},
        {"type": "way", "id": 4, "tags": {"leisure": "park"}},
    ]
    table, report = normalize(payload, NOW)
    assert table.num_rows == 2
    assert report["records_invalid"] == 2
    assert report["records_duplicate"] == 1
    assert len(report["issues"]) == 3


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"elements": []},
        {"elements": [], "remark": "timeout"},
        {"elements": [{"type": "node", "id": 1}]},
    ],
)
def test_incomplete_or_wrong_city_rejected(payload):
    with pytest.raises(CollectionError):
        check_payload(payload)


def test_query_city_and_all_requested_types():
    query = build_query(180)
    assert '"wikidata"="Q919"' in query
    assert "map_to_area" in query and "out meta center" in query
    for tag in [
        "school",
        "kindergarten",
        "college",
        "university",
        "hospital",
        "clinic",
        "pharmacy",
        "park",
        "forest",
        "playground",
        "supermarket",
        "mall",
        "sports_centre",
        "fitness_centre",
        "bus_stop",
        "tram_stop",
        "station",
    ]:
        assert tag in query


def test_retry_transient_error(monkeypatch):
    calls = []

    def get(self, url, **kwargs):
        calls.append(url)
        return httpx.Response(
            503 if len(calls) == 1 else 200,
            content=b'{"elements": []}',
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.Client, "get", get)
    assert fetch(Settings(backoff_seconds=0), "query") == b'{"elements": []}'
    assert len(calls) == 2


def test_offline_pipeline_reproducible_and_checksum(tmp_path):
    raw = tmp_path / "raw.json"
    raw.write_text(json.dumps(fixture_payload()), encoding="utf-8")
    write_json(
        raw.with_suffix(".metadata.json"),
        {
            "collected_at": NOW.isoformat(),
            "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
        },
    )
    settings = Settings(data_dir=tmp_path)
    preprocess(settings, raw)
    first = pq.read_table(tmp_path / "processed/geo_objects.parquet")
    preprocess(settings, raw)
    assert first.equals(pq.read_table(tmp_path / "processed/geo_objects.parquet"))
    raw.write_text("{}", encoding="utf-8")
    with pytest.raises(CollectionError, match="checksum"):
        preprocess(settings, raw)


def test_collect_archives_error_before_validation(tmp_path, monkeypatch):
    content = b'{"remark": "query timed out", "elements": []}'
    monkeypatch.setattr("krasnoyarsk_ml.pipeline.fetch", lambda *args: content)
    with pytest.raises(CollectionError, match="incomplete"):
        collect(Settings(data_dir=tmp_path))
    raw_files = list((tmp_path / "raw/osm").glob("*/*.json"))
    assert any(path.read_bytes() == content for path in raw_files)
    assert not list((tmp_path / "raw/osm").glob("*.json"))


def test_collect_to_parquet_end_to_end(tmp_path, monkeypatch):
    content = json.dumps(fixture_payload()).encode()
    monkeypatch.setattr("krasnoyarsk_ml.pipeline.fetch", lambda *args: content)
    settings = Settings(data_dir=tmp_path)
    raw = collect(settings)
    report = preprocess(settings, raw)
    assert report["records_valid"] == 2
    assert pq.read_table(tmp_path / "processed/geo_objects.parquet").num_rows == 2


def test_permanent_http_error_is_not_retried(monkeypatch):
    calls = []

    def get(self, url, **kwargs):
        calls.append(url)
        return httpx.Response(400, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.Client, "get", get)
    with pytest.raises(CollectionError, match="400"):
        fetch(Settings(backoff_seconds=0), "query")
    assert len(calls) == 1


def test_naive_source_timestamp_rejected():
    payload = fixture_payload()
    payload["elements"][1]["timestamp"] = "2025-01-01T00:00:00"
    table, report = normalize(payload, NOW)
    assert table.num_rows == 1
    assert report["records_invalid"] == 1
