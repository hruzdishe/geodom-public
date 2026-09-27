import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pydantic import ValidationError

from krasnoyarsk_ml import scoring
from krasnoyarsk_ml.features import GEOD, METHOD, VERSION
from krasnoyarsk_ml.features import run as features_run
from krasnoyarsk_ml.scoring import Preferences, ScoringConfig, recommend, resolved_weights


def home(identifier, **overrides):
    return {
        "id": identifier,
        "price": 8_000_000,
        "rooms": 2,
        "currency": "RUB",
        "offer_type": "sale",
        "district_name": "Советский",
        "lat": 0.0,
        "lon": 0.0,
    } | overrides


def feature(identifier, **distances):
    result = {"apartment_id": identifier, "feature_version": VERSION, "distance_method": METHOD}
    for group, distance in distances.items():
        result.update(
            {
                f"{group}_nearest_distance_m": distance,
                f"{group}_nearest_poi_id": f"osm:{group}" if distance is not None else None,
                f"{group}_observed_in_snapshot": distance is not None,
            }
        )
    return result


def at_minutes(identifier, minutes, speed=30):
    lon, lat, _ = GEOD.fwd(0, 0, 90, minutes / 60 * speed * 1000)
    return home(identifier, lon=lon, lat=lat)


def test_hard_price_rooms_and_district_filters_are_not_relaxed():
    apartments = [
        home("min", price=6_000_000),
        home("max", price=12_000_000),
        home("cheap", price=5_999_999),
        home("expensive", price=12_000_001),
        home("studio", rooms=0),
        home("other", district_name="Центральный"),
    ]
    result = recommend(
        apartments,
        [],
        {"price_min": 6_000_000, "price_max": 12_000_000, "rooms": [2], "districts": ["Советский"]},
    )
    assert {r["apartment_id"] for r in result["results"]} == {"min", "max"}
    assert result["filter_rejection_counts"]["price"] == 2
    empty = recommend(apartments, [], {"rooms": [10]})
    assert empty["status"] == "no_matches" and empty["results"] == []
    assert recommend([home("studio", rooms=0)], [], {"rooms": [0]})["eligible_count"] == 1


def test_sale_data_does_not_become_rental_data():
    result = recommend([home("a")], [], {"offer_type": "rent"})
    assert result["eligible_count"] == 0


def test_family_defaults_and_manual_override_including_zero():
    weights, _ = resolved_weights(Preferences(children_age_groups=["preschool", "school"]))
    assert weights == {"kindergartens": 5, "schools": 5}
    weights, _ = resolved_weights(
        Preferences(
            children_age_groups=["preschool", "school"],
            priorities={"schools": 0, "kindergartens": 2},
        )
    )
    assert weights == {"kindergartens": 2}
    assert resolved_weights(Preferences())[0] == {}


def test_family_profiles_change_order_using_the_relevant_facility():
    homes = [home("school_near"), home("garden_near")]
    features = [
        feature("school_near", school=100, kindergarten=2000),
        feature("garden_near", school=2000, kindergarten=100),
    ]
    for age, expected in [("school", "school_near"), ("preschool", "garden_near")]:
        result = recommend(homes, features, {"children_age_groups": [age]})
        assert result["results"][0]["apartment_id"] == expected


def test_commute_is_soft_and_exactly_fifteen_percent_is_within_tolerance():
    apartments = [
        at_minutes("desired", 40),
        at_minutes("grace", 44),
        at_minutes("boundary", 46),
        at_minutes("late", 46.001),
        at_minutes("far", 90),
    ]
    result = recommend(
        apartments,
        [],
        {"work": {"lat": 0, "lon": 0, "max_minutes": 40}},
        config={"assumed_car_speed_kmh": 30},
    )
    assert result["eligible_count"] == 5
    rows = {r["apartment_id"]: r for r in result["results"]}
    assert rows["desired"]["commute"]["status"] == "within_target"
    assert rows["grace"]["commute"]["status"] == "within_tolerance"
    assert rows["boundary"]["commute"]["exceeds_time_with_tolerance"] is False
    assert rows["late"]["commute"]["exceeds_time_with_tolerance"] is True
    assert rows["far"]["commute"]["badge"]
    assert rows["desired"]["score"] > rows["far"]["score"]
    assert rows["boundary"]["commute"]["is_routed"] is False


def test_minutes_are_not_invented_without_an_explicit_speed():
    result = recommend([at_minutes("a", 50)], [], {"work": {"lat": 0, "lon": 0, "max_minutes": 40}})
    commute = result["results"][0]["commute"]
    assert commute["status"] == "distance_only"
    assert commute["distance_m"] == pytest.approx(25000, abs=0.001)
    assert commute["estimated_minutes"] is None and commute["exceeds_time_with_tolerance"] is None


def test_unsupported_priorities_are_reported_and_not_fabricated():
    result = recommend(
        [home("a")],
        [feature("a", school=100)],
        {"priorities": {"ecology": 5, "safety": 5, "cafes": 2}},
    )
    assert result["status"] == "no_supported_priorities"
    assert len(result["unsupported_priorities"]) == 3
    assert result["results"][0]["score"] is None


def test_missing_data_does_not_boost_score_by_renormalization():
    result = recommend(
        [home("complete"), home("partial"), home("unknown")],
        [feature("complete", school=100, park=100), feature("partial", school=100)],
        {"priorities": {"schools": 5, "parks": 5}},
    )
    rows = {r["apartment_id"]: r for r in result["results"]}
    assert rows["complete"]["score"] > rows["partial"]["score"]
    assert rows["partial"]["score_coverage"] == 0.5
    assert rows["partial"]["score_upper_bound"] > rows["partial"]["score"]
    assert rows["unknown"]["score"] is None
    assert result["results"][-1]["apartment_id"] == "unknown"
    assert "unknown" in result["missing_feature_ids"]


def test_score_does_not_depend_on_other_candidates_or_input_order():
    prefs = {"priorities": {"schools": 5}}
    one = recommend([home("a")], [feature("a", school=500)], prefs)
    many = recommend(
        [home("b"), home("a"), home("z")],
        [feature("z", school=2000), feature("b", school=500), feature("a", school=500)],
        prefs,
    )
    assert one["results"][0]["score"] == 50
    assert many["results"][0]["apartment_id"] == "a"
    assert many["results"][0]["score"] == one["results"][0]["score"]


def test_bad_work_coordinates_do_not_silently_drop_the_apartment():
    result = recommend([home("a", lat=None)], [], {"work": {"lat": 0, "lon": 0}})
    assert result["eligible_count"] == 1
    assert result["results"][0]["commute"]["status"] == "unavailable"
    assert result["results"][0]["score"] is None


@pytest.mark.parametrize(
    "prefs",
    [
        {"price_min": 10, "price_max": 5},
        {"rooms": [-1]},
        {"priorities": {"schools": 6}},
        {"priorities": {"typo": 2}},
        {"work": {"lat": 92, "lon": 56}},
        {"work": {"lat": float("nan"), "lon": 56}},
        {"priorities": {"schools": True}},
    ],
)
def test_invalid_preferences_rejected(prefs):
    with pytest.raises(ValidationError):
        Preferences.model_validate(prefs)


def test_duplicate_features_and_incompatible_versions_rejected():
    with pytest.raises(ValueError, match="unique"):
        recommend([home("a")], [feature("a"), feature("a")], {})
    bad = feature("a") | {"feature_version": "unknown"}
    with pytest.raises(ValueError, match="Incompatible"):
        recommend([home("a")], [bad], {})
    with pytest.raises(ValidationError):
        ScoringConfig(assumed_car_speed_kmh=0)


def test_cli_round_trip_and_stale_apartment_detection(tmp_path, monkeypatch):
    apartments, pois, metadata = (
        tmp_path / n for n in ("apartments.parquet", "pois.parquet", "meta.json")
    )
    pq.write_table(pa.Table.from_pylist([home("a")]), apartments)
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "id": "osm:1",
                    "lat": 0.001,
                    "lon": 0.0,
                    "subcategory": "school",
                    "geometry_kind": "osm_node",
                }
            ]
        ),
        pois,
    )
    metadata.write_text('{"timestamp_osm_base":"2026-05-31T00:00:00Z"}', encoding="utf-8")
    feature_dir = tmp_path / "features"
    features_run(apartments, pois, metadata, feature_dir)
    prefs, output = tmp_path / "preferences.json", tmp_path / "result.json"
    prefs.write_text('{"children_age_groups":["school"]}', encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "ml-recommend",
            "--apartments",
            str(apartments),
            "--features",
            str(feature_dir / "apartment_features.parquet"),
            "--feature-report",
            str(feature_dir / "feature_report.json"),
            "--preferences",
            str(prefs),
            "--output",
            str(output),
        ],
    )
    assert scoring.main() == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["results"][0]["apartment_id"] == "a"
    assert result["results"][0]["poi_snapshot_at"].startswith("2026-05-31")
    pq.write_table(pa.Table.from_pylist([home("a", lon=0.01)]), apartments)
    with pytest.raises(ValueError, match="recompute features"):
        scoring.main()


def test_enabled_commute_filter_rejects_above_limit_before_ranking():
    result = recommend(
        [at_minutes('near',10),at_minutes('boundary',20),at_minutes('far',20.001)], [],
        {'work':{'lat':0,'lon':0,'max_minutes':20}},
        config={'assumed_car_speed_kmh':30,'enforce_max_commute':True},
    )
    assert result['eligible_count'] == 2
    assert {r['apartment_id'] for r in result['results']} == {'near','boundary'}
    assert result['filter_rejection_counts']['commute'] == 1
    assert all(r['commute']['estimated_minutes'] <= 20 for r in result['results'])


def test_enabled_commute_filter_excludes_unknown_coordinates():
    row=home('unknown')
    row['lat']=None
    result=recommend([row],[],{'work':{'lat':0,'lon':0,'max_minutes':20}},
        config={'assumed_car_speed_kmh':30,'enforce_max_commute':True})
    assert result['eligible_count']==0
    assert result['filter_rejection_counts']['commute']==1
