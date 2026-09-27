from datetime import UTC, datetime

import pytest

from krasnoyarsk_ml.addresses import enrich
from krasnoyarsk_ml.normalize import normalize


def boundary():
    return {"type": "relation", "id": 1430616, "tags": {"place": "city", "wikidata": "Q919"}}


def reference():
    return {
        "elements": [
            boundary(),
            {
                "type": "way",
                "id": 100,
                "tags": {
                    "building": "yes",
                    "addr:street": "Тестовая улица",
                    "addr:housenumber": "10",
                },
                "geometry": [
                    {"lat": lat, "lon": lon}
                    for lon, lat in [
                        (92.8999, 55.9999),
                        (92.9001, 55.9999),
                        (92.9001, 56.0001),
                        (92.8999, 56.0001),
                        (92.8999, 55.9999),
                    ]
                ],
            },
            {
                "type": "way",
                "id": 200,
                "tags": {"highway": "residential", "name": "Другая улица"},
                "geometry": [{"lon": 92.91, "lat": 55.999}, {"lon": 92.91, "lat": 56.001}],
            },
        ]
    }


def poi_table(lon=92.9, kind="node", tags=None):
    poi = {"type": kind, "id": 1, "tags": {"amenity": "school"} | (tags or {})}
    if kind == "node":
        poi.update(lon=lon, lat=56.0)
    else:
        poi["center"] = {"lon": lon, "lat": 56.0}
    table, _ = normalize({"elements": [boundary(), poi]}, datetime(2026, 9, 26, tzinfo=UTC))
    return table


def test_node_in_building_inherits_address_but_bbox_center_does_not():
    table, _ = enrich(poi_table(), reference())
    row = table.to_pylist()[0]
    assert row["address"] == "Тестовая улица 10"
    assert row["address_method"] == "containing_building"
    assert row["address_source_id"] == "way/100"
    assert row["address_is_approximate"] is False
    bbox, _ = enrich(poi_table(kind="way"), reference())
    assert bbox.to_pylist()[0]["address"] == "Рядом с: Тестовая улица 10"
    assert bbox.to_pylist()[0]["address_is_approximate"] is True


def test_nearby_house_uses_metric_distance_and_explicit_hint():
    table, _ = enrich(poi_table(lon=92.9005), reference())
    row = table.to_pylist()[0]
    assert row["address_method"] == "nearby_address"
    assert 24 < row["address_distance_m"] < 26
    assert row["address"].startswith("Рядом с:")


def test_street_fallback_and_maximum_distance():
    street, _ = enrich(poi_table(lon=92.9105), reference())
    assert street.to_pylist()[0]["address"] == "Рядом с: Другая улица"
    far, _ = enrich(poi_table(lon=93.0), reference())
    row = far.to_pylist()[0]
    assert row["address"] is None
    assert row["address_method"] == "missing"
    assert "координаты" in row["location_label"]


def test_original_address_preserved_and_enrichment_idempotent():
    table, _ = enrich(poi_table(tags={"addr:full": "Собственный адрес"}), reference())
    assert table.to_pylist()[0]["address"] == "Собственный адрес"
    repeated, _ = enrich(table, reference())
    assert repeated.equals(table)


def test_invalid_reference_geometry_reported():
    payload = reference()
    payload["elements"][1]["geometry"][0]["lat"] = 500
    _, report = enrich(poi_table(), payload)
    assert len(report["reference_issues"]) == 1


def test_zero_distance_threshold_rejected():
    with pytest.raises(ValueError, match="positive"):
        enrich(poi_table(), reference(), max_address_m=0)
