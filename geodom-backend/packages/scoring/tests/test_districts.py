import copy
import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from shapely.geometry import Point, box, mapping
from shapely.ops import transform

from krasnoyarsk_ml.district_environment import normalize_air
from krasnoyarsk_ml.district_geometry import (
    TO_METRIC,
    TO_WGS84,
    audit_apartments,
    build_grid,
    osm_polygon,
)
from krasnoyarsk_ml.districts import VERSION, rank_districts, verified_manifest
from krasnoyarsk_ml.features import GEOD, METHOD
from krasnoyarsk_ml.features import VERSION as FEATURE_VERSION


def districts():
    return [{"district_id": key, "district_name": key} for key in ("a", "b")]


def point(key, district="a", weight=1, **kwargs):
    return {
        "id": key,
        "district_id": district,
        "weight_m2": weight,
        "lat": 56.0,
        "lon": 93.0,
    } | kwargs


def feature(key, **distances):
    result = {"point_id": key, "feature_version": FEATURE_VERSION, "distance_method": METHOD}
    for category, distance in distances.items():
        result.update(
            {
                f"{category}_observed_in_snapshot": distance is not None,
                f"{category}_nearest_distance_m": distance,
            }
        )
    return result


def test_weighted_point_scores_not_score_of_average_distance():
    result = rank_districts(
        districts(),
        [point("a1", weight=9), point("a2"), point("b1", "b")],
        [feature("a1", school=0), feature("a2", school=1000), feature("b1", school=500)],
        {"priorities": {"schools": 5}},
    )
    assert [r["district_id"] for r in result["results"]] == ["a", "b"]
    assert result["results"][0]["score"] == pytest.approx(92)
    assert result["results"][1]["score"] == pytest.approx(50)
    assert result["results"][0]["components"][0]["median_distance_m"] == 0


def test_missing_area_cannot_increase_score_by_renormalizing():
    result = rank_districts(
        districts(),
        [point("a1", weight=1), point("a2", weight=9), point("b1", "b")],
        [feature("a1", school=0), feature("b1", school=500)],
        {"priorities": {"schools": 5}},
    )
    a = next(r for r in result["results"] if r["district_id"] == "a")
    assert a["score"] == pytest.approx(10)
    assert a["score_upper_bound"] == pytest.approx(100)
    assert a["score_coverage"] == pytest.approx(0.1)
    assert result["results"][0]["district_id"] == "b"


def test_missing_category_keeps_its_weight():
    result = rank_districts(
        districts(),
        [point("a"), point("b", "b")],
        [feature("a", school=0), feature("b", school=0, park=700)],
        {"priorities": {"schools": 1, "parks": 1}},
    )
    a = next(r for r in result["results"] if r["district_id"] == "a")
    assert (a["score"], a["score_upper_bound"], a["score_coverage"]) == (50, 100, 0.5)


def test_family_defaults_manual_zero_and_unsupported_evidence():
    args = (
        districts(),
        [point("a"), point("b", "b")],
        [feature("a", school=0, kindergarten=2000), feature("b", school=2000, kindergarten=0)],
    )
    school = rank_districts(*args, {"children_age_groups": ["school"]})
    preschool = rank_districts(*args, {"children_age_groups": ["preschool"]})
    assert school["results"][0]["district_id"] == "a"
    assert preschool["results"][0]["district_id"] == "b"
    no = rank_districts(
        *args,
        {
            "children_age_groups": ["school"],
            "priorities": {"schools": 0, "ecology": 5, "safety": 5},
        },
        external_evidence={"a": {"air": {"score": 100}}},
    )
    assert no["status"] == "no_supported_priorities"
    assert len(no["unsupported_priorities"]) == 2
    assert all(
        r["score"] is None and r["rank"] is None and r["ecology_score"] is None
        for r in no["results"]
    )


def test_all_unknown_remains_unknown():
    result = rank_districts(
        districts(), [point("a"), point("b", "b")], [], {"priorities": {"schools": 5}}
    )
    assert all(r["score"] is None and r["score_coverage"] == 0 for r in result["results"])


@pytest.mark.parametrize("minutes,expected", [(40, 0), (46, 0), (46.001, 1)])
def test_commute_tolerance_uses_raw_time_and_never_filters_district(minutes, expected):
    lon, lat, _ = GEOD.fwd(93, 56, 90, minutes / 60 * 30 * 1000)
    points = [point("a", lon=lon, lat=lat), point("b", "b")]
    result = rank_districts(
        districts(),
        points,
        [],
        {"work": {"lat": 56, "lon": 93, "max_minutes": 40}},
        {"assumed_car_speed_kmh": 30},
    )
    a = next(r for r in result["results"] if r["district_id"] == "a")
    assert a["components"][0]["share_beyond_time_tolerance"] == expected
    assert len(result["results"]) == 2
    assert result["commute"]["warning_threshold_minutes"] == 46


def test_commute_without_speed_has_no_time_assertion():
    result = rank_districts(
        districts(),
        [point("a"), point("b", "b")],
        [],
        {"work": {"lat": 56, "lon": 93, "max_minutes": 40}},
    )
    assert result["results"][0]["components"][0]["share_beyond_time_tolerance"] is None


def test_listing_density_does_not_change_rating_and_truncation_is_rejected():
    args = (
        districts(),
        [point("a"), point("b", "b")],
        [feature("a", school=500), feature("b", school=500)],
        {"priorities": {"schools": 1}},
    )
    baseline = rank_districts(*args)
    apartments = {
        "returned_count": 20,
        "eligible_count": 20,
        "results": [
            {"apartment_id": str(i), "apartment": {"district_name": "a"}} for i in range(20)
        ],
    }
    dense = rank_districts(*args, apartment_result=apartments)
    assert [r["score"] for r in baseline["results"]] == [r["score"] for r in dense["results"]]
    assert dense["results"][0]["matching_listing_count"] == 20
    assert dense["results"][1]["matching_listing_count"] == 0
    assert dense["results"][0]["top_apartment_ids"] == ["0", "1", "2"]
    with pytest.raises(ValueError, match="all eligible"):
        rank_districts(*args, apartment_result=apartments | {"returned_count": 10})


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "unknown_district",
        "nan_weight",
        "zero_weight",
        "bad_coords",
        "orphan_features",
        "bad_version",
    ],
)
def test_bad_inputs_are_rejected(mutation):
    points = [point("a"), point("b", "b")]
    features = [feature("a", school=100)]
    if mutation == "duplicate":
        points.append(points[0])
    elif mutation == "unknown_district":
        points[0]["district_id"] = "other"
    elif mutation == "nan_weight":
        points[0]["weight_m2"] = float("nan")
    elif mutation == "zero_weight":
        points[0]["weight_m2"] = 0
    elif mutation == "bad_coords":
        points[0]["lat"] = 200
    elif mutation == "orphan_features":
        features[0]["point_id"] = "other"
    else:
        features[0]["feature_version"] = "bad"
    with pytest.raises(ValueError):
        rank_districts(districts(), points, features, {"priorities": {"schools": 1}})


def geojson_for(polygons):
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"district_id": str(i), "district_name": str(i)},
                "geometry": mapping(transform(TO_WGS84, polygon)),
            }
            for i, polygon in enumerate(polygons)
        ],
    }


def test_grid_conserves_residential_area_and_points_stay_inside_disconnected_parts():
    district = box(500000, 6200000, 500500, 6200500)
    residential = box(500010, 6200010, 500050, 6200050).union(box(500100, 6200100, 500200, 6200200))
    points, summary = build_grid(geojson_for([district]), residential, 250)
    assert len(points) == 2
    assert sum(p["weight_m2"] for p in points) == pytest.approx(residential.area, abs=0.001)
    assert summary[0]["mapped_residential_area_km2"] == pytest.approx(residential.area / 1e6)
    assert all(residential.covers(transform(TO_METRIC, Point(p["lon"], p["lat"]))) for p in points)


def test_geometry_holes_are_preserved_and_open_rings_fail():
    outer = [{"lon": x, "lat": y} for x, y in box(0, 0, 10, 10).exterior.coords]
    inner = [{"lon": x, "lat": y} for x, y in box(2, 2, 4, 4).exterior.coords]
    element = {
        "type": "relation",
        "members": [
            {"type": "way", "role": "outer", "geometry": outer},
            {"type": "way", "role": "inner", "geometry": inner},
        ],
    }
    assert osm_polygon(element).area == 96
    bad = copy.deepcopy(element)
    bad["members"][0]["geometry"].pop()
    with pytest.raises(ValueError, match="Disconnected"):
        osm_polygon(bad)


def test_apartment_audit_reports_source_mismatch_and_outside():
    district = box(500000, 6200000, 500500, 6200500)
    point_wgs = transform(TO_WGS84, district.centroid)
    rows = audit_apartments(
        [
            {"id": "a", "district_name": "wrong", "lon": point_wgs.x, "lat": point_wgs.y},
            {"id": "b", "district_name": "0", "lon": 0, "lat": 0},
        ],
        geojson_for([district]),
        district,
    )
    assert rows[0]["status"] == "listing_geometry_mismatch"
    assert rows[1]["status"] == "outside_boundaries"


def test_manifest_rejects_tampered_output(tmp_path):
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "status": "complete",
                "version": VERSION,
                "outputs": {"file.json": {"sha256": "wrong"}},
            }
        )
    )
    (tmp_path / "file.json").write_text("{}")
    with pytest.raises(ValueError, match="checksum"):
        verified_manifest(tmp_path)


def air_catalog():
    return {
        "data": {
            "sites": [
                {
                    "id": 1,
                    "name": "test",
                    "geom_x": 93,
                    "geom_y": 56,
                    "end_date": "2023-01-01 00:00:00",
                }
            ]
        }
    }


def test_air_no_zero_fill_activity_conflicts_and_duplicate_days_reported():
    payload = {
        "status": {"code": 1},
        "data": [
            {"site": 1, "time": "2025-01-01 00:00:00", "pm25": 10},
            {"site": 1, "time": "2025-01-02 00:00:00", "pm25": None},
            {"site": 1, "time": "2025-01-03 00:00:00", "pm25": -1},
        ],
    }
    obs, stations, report = normalize_air(air_catalog(), [payload, payload], 2025)
    assert len(obs) == 1 and obs[0]["catalog_activity_conflict"] is True
    assert stations[0]["day_coverage"] == pytest.approx(1 / 365)
    assert stations[0]["observed_daily_mean_pm25_ug_m3"] == 10
    assert report["deduplicated_boundary_days"] == 1
    assert stations[0]["hourly_completeness_verified"] is False


def test_air_conflicting_duplicate_is_not_silently_overwritten():
    payload = {
        "status": {"code": 1},
        "data": [
            {"site": 1, "time": "2025-01-01 00:00:00", "pm25": 10},
            {"site": 1, "time": "2025-01-01 00:00:00", "pm25": 20},
        ],
    }
    with pytest.raises(ValueError, match="Conflicting"):
        normalize_air(air_catalog(), [payload], 2025)


def test_file_pipeline_spatial_join_hard_filters_and_stale_snapshot(tmp_path):
    from datetime import UTC, datetime

    from krasnoyarsk_ml.district_geometry import sha256
    from krasnoyarsk_ml.districts import build, recommend_from_files
    from krasnoyarsk_ml.features import calculate
    from krasnoyarsk_ml.housing.sibdom import DISTRICTS
    from krasnoyarsk_ml.pipeline import write_json

    raw = tmp_path / "raw"
    raw.mkdir()
    elements, residential = [], []
    names = list(DISTRICTS.values())
    for i, name in enumerate(names):
        geometry = box(93 + i * 0.01, 56, 93 + i * 0.01 + 0.005, 56.005)
        coords = [{"lon": x, "lat": y} for x, y in geometry.exterior.coords]
        elements.append(
            {
                "type": "relation",
                "id": i + 1,
                "version": 1,
                "tags": {"name": name + " район", "boundary": "administrative"},
                "members": [{"type": "way", "role": "outer", "geometry": coords}],
            }
        )
        residential.append(
            {"type": "way", "id": i + 100, "tags": {"landuse": "residential"}, "geometry": coords}
        )
    source_meta = {"timestamp_osm_base": "2025-01-01T00:00:00Z"}
    write_json(raw / "boundaries.json", {"elements": elements, "osm3s": source_meta})
    write_json(raw / "residential.json", {"elements": residential, "osm3s": source_meta})
    pois = pa.Table.from_pylist(
        [
            {
                "id": "school",
                "subcategory": "school",
                "geometry_kind": "osm_node",
                "lat": 56.002,
                "lon": 93.002,
            }
        ]
    )
    base = {
        "lat": 56.002,
        "lon": 93.002,
        "rooms": 2,
        "price": 8_000_000,
        "currency": "RUB",
        "offer_type": "sale",
        "district_name": names[1],
    }
    homes = pa.Table.from_pylist(
        [
            base | {"id": "good"},
            base | {"id": "expensive", "price": 15_000_000},
            base | {"id": "studio", "rooms": 0},
        ]
    )
    apartment_path, poi_path = tmp_path / "apartments.parquet", tmp_path / "pois.parquet"
    pq.write_table(homes, apartment_path)
    pq.write_table(pois, poi_path)
    meta_path = tmp_path / "poi_meta.json"
    write_json(meta_path, source_meta)
    features, _, _ = calculate(homes, pois, snapshot_at=datetime(2025, 1, 1, tzinfo=UTC))
    feature_path, report_path = tmp_path / "features.parquet", tmp_path / "report.json"
    pq.write_table(features, feature_path)
    write_json(
        report_path,
        {
            "status": "complete",
            "inputs": {"apartments": {"sha256": sha256(apartment_path)}},
            "outputs": {"apartment_features.parquet": {"sha256": sha256(feature_path)}},
        },
    )
    directory = tmp_path / "districts"
    report = build(raw, directory, poi_path, meta_path, apartment_path)
    assert report["district_count"] == 7
    assert report["apartment_audit"] == {"listing_geometry_mismatch": 3}
    preferences = {"price_max": 12_000_000, "rooms": [2], "priorities": {"schools": 5}}
    result = recommend_from_files(directory, apartment_path, feature_path, report_path, preferences)
    assert sum(r["matching_listing_count"] for r in result["results"]) == 1
    assert result["results"][0]["district_name"] == names[0]
    assert result["results"][0]["top_apartment_ids"] == ["good"]
    assert pq.read_table(apartment_path).to_pylist()[0]["district_name"] == names[1]
    empty = recommend_from_files(
        directory, apartment_path, feature_path, report_path, preferences | {"rooms": [10]}
    )
    assert sum(r["matching_listing_count"] for r in empty["results"]) == 0
    assert [r["score"] for r in empty["results"]] == [r["score"] for r in result["results"]]
    # Different data with unchanged old report must fail before issuing recommendations.
    pq.write_table(pa.Table.from_pylist([base | {"id": "changed"}]), apartment_path)
    with pytest.raises(ValueError, match="snapshots differ"):
        recommend_from_files(directory, apartment_path, feature_path, report_path, preferences)
