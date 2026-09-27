import hashlib
import json
import math
from datetime import UTC, datetime

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from krasnoyarsk_ml.features import GEOD, GROUPS, calculate, run

NOW = datetime(2026, 9, 26, tzinfo=UTC)


def homes(rows=None):
    return pa.Table.from_pylist(rows or [{"id": "apt:1", "lat": 0.0, "lon": 0.0}])


def pois(rows):
    return pa.Table.from_pylist(
        rows,
        schema=pa.schema(
            [
                ("id", pa.string()),
                ("lat", pa.float64()),
                ("lon", pa.float64()),
                ("subcategory", pa.string()),
                ("geometry_kind", pa.string()),
                ("address", pa.string()),
            ]
        ),
    )


def point(identifier, distance, group="school", geometry="osm_node"):
    lon, lat, _ = GEOD.fwd(0, 0, 90, distance)
    return {
        "id": identifier,
        "lat": lat,
        "lon": lon,
        "subcategory": group,
        "geometry_kind": geometry,
        "address": "Approximate address does not change coordinates",
    }


def compute(objects):
    return calculate(homes(), pois(objects), computed_at=NOW)


def test_equatorial_reference_metres_not_degrees():
    p = point("osm:a", 1)
    p.update(lon=1.0, lat=0.0)
    wide, nearest, _ = compute([p])
    # Known equatorial WGS84 arc for one degree; independent analytic reference.
    expected = 6378137 * math.pi / 180
    row = wide.to_pylist()[0]
    assert row["school_nearest_distance_m"] == pytest.approx(expected, abs=0.001)
    assert row["school_count_1000m"] == 0
    assert (
        next(r for r in nearest.to_pylist() if r["feature_group"] == "school")["poi_id"] == "osm:a"
    )


def test_inclusive_boundaries_use_unrounded_distances():
    distances = [499.9996, 500, 500.0004, 1000, 1000.0004]
    wide, _, _ = compute([point(f"osm:{i}", d) for i, d in enumerate(distances)])
    row = wide.to_pylist()[0]
    assert row["school_count_500m"] == 2
    assert row["school_count_1000m"] == 4


def test_missing_group_is_null_distance_and_unverified_zero_count():
    wide, nearest, report = compute([])
    row = wide.to_pylist()[0]
    assert row["school_nearest_distance_m"] is None
    assert row["school_nearest_poi_id"] is None
    assert row["school_count_500m"] == row["school_count_1000m"] == 0
    assert row["school_observed_in_snapshot"] is False
    assert row["poi_coverage_verified"] is False
    assert nearest.num_rows == len(GROUPS)
    assert nearest["poi_id"].null_count == len(GROUPS)
    assert report["poi_snapshot_at"] is None
    assert pa.types.is_floating(wide.schema.field("school_nearest_distance_m").type)


def test_transport_group_and_geometry_flags():
    wide, nearest, _ = compute(
        [
            point("bus", 30, "bus_stop", "bbox_center"),
            point("tram", 50, "tram_stop"),
            point("train", 1, "station"),
        ]
    )
    row = wide.to_pylist()[0]
    assert row["public_transport_nearest_poi_id"] == "bus"
    assert row["public_transport_count_500m"] == 2
    assert row["station_nearest_poi_id"] == "train"
    detail = next(r for r in nearest.to_pylist() if r["feature_group"] == "public_transport")
    assert detail["poi_is_bbox_center"] is True


def test_ties_and_input_order_are_deterministic_zero_distance_is_valid():
    points = [point("osm:z", 0), point("osm:a", 0)]
    first, _, _ = compute(points)
    second, _, _ = compute(points[::-1])
    assert first.equals(second)
    row = first.to_pylist()[0]
    assert row["school_nearest_poi_id"] == "osm:a"
    assert row["school_nearest_distance_m"] == 0
    # Different OSM identities are counted separately even at the same location.
    assert row["school_count_500m"] == 2


@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), 91.0])
def test_invalid_coordinates_fail_instead_of_producing_false_zeros(value):
    with pytest.raises(ValueError, match="invalid lat"):
        calculate(homes([{"id": "bad", "lat": value, "lon": 0.0}]), pois([]))


def test_duplicate_poi_ids_fail_instead_of_double_counting():
    with pytest.raises(ValueError, match="duplicate ID"):
        compute([point("osm:a", 10), point("osm:a", 20)])


def test_unknown_category_is_not_silently_ignored():
    with pytest.raises(ValueError, match="Unknown POI subcategory"):
        compute([point("osm:a", 10, "unexpected")])


def test_offline_export_preserves_ids_types_snapshot_and_checksums(tmp_path):
    a, p, metadata = (
        tmp_path / "apartments.parquet",
        tmp_path / "pois.parquet",
        tmp_path / "meta.json",
    )
    pq.write_table(homes(), a)
    pq.write_table(pois([point("osm:a", 100)]), p)
    metadata.write_text(
        json.dumps({"timestamp_osm_base": "2026-05-31T22:37:44Z"}), encoding="utf-8"
    )
    output = tmp_path / "features"
    report = run(a, p, metadata, output)
    assert report["status"] == "complete"
    table = pq.read_table(output / "apartment_features.parquet")
    assert table["apartment_id"].to_pylist() == ["apt:1"]
    assert table["poi_snapshot_at"][0].as_py() == datetime(2026, 5, 31, 22, 37, 44, tzinfo=UTC)
    row = json.loads((output / "apartment_features.jsonl").read_text(encoding="utf-8"))
    assert row["school_nearest_distance_m"] == 100
    for filename, info in report["outputs"].items():
        assert hashlib.sha256((output / filename).read_bytes()).hexdigest() == info["sha256"]
