"""Offline district features and preference ranking, independent of listing density."""

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .config import Settings
from .district_geometry import (
    audit_apartments,
    build_grid,
    collect_geometry,
    district_polygons,
    residential_mask,
    sha256,
    write_parquet,
)
from .features import METHOD, calculate
from .features import VERSION as FEATURE_VERSION
from .pipeline import write_json
from .scoring import (
    PRIORITIES,
    Preferences,
    ScoringConfig,
    commute,
    coordinates,
    finite_number,
    infrastructure_component,
    recommend,
    resolved_weights,
    utility,
)

VERSION = "district_scoring_v1"
DEFAULT_OUTPUT = Path("data/processed/districts")
WARNINGS = [
    "Рейтинг описывает нанесённую на OSM жилую территорию; полнота покрытия не подтверждена.",
    "Вес точки — площадь жилого участка, не количество жителей или квартир.",
    "Границы OSM не сверены с актуальными официальными границами; версия указана в данных.",
    "POI неполны; доступность школы не означает качество образования.",
    "Расстояния по прямой, без маршрутов, мостов и пробок.",
    "score_coverage описывает доступность выбранных компонентов, а не полноту карты OSM.",
]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def weighted_quantile(values: list[tuple[float, float]], quantile: float):
    if not values:
        return None
    target = sum(weight for _, weight in values) * quantile
    cumulative = 0.0
    for value, weight in sorted(values):
        cumulative += weight
        if cumulative >= target:
            return value
    return max(v for v, _ in values)


def validate_points(districts: list[dict], points: list[dict], features: list[dict]) -> dict:
    district_ids = [r["district_id"] for r in districts]
    if len(set(district_ids)) != len(district_ids) or not district_ids:
        raise ValueError("Empty or duplicate districts")
    seen, covered = set(), set()
    for point in points:
        identifier = point.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise ValueError("Invalid or duplicate point IDs")
        seen.add(identifier)
        if point.get("district_id") not in district_ids:
            raise ValueError("Point belongs to unknown district")
        if (
            not coordinates(point)
            or not finite_number(point.get("weight_m2"))
            or point["weight_m2"] <= 0
        ):
            raise ValueError("Invalid reference point coordinates or weight")
        covered.add(point["district_id"])
    if covered != set(district_ids):
        raise ValueError("District without reference points")
    by_id = {}
    for feature in features:
        identifier = feature.get("point_id")
        if identifier in by_id or identifier not in seen:
            raise ValueError("Duplicate or orphan reference point feature")
        if (
            feature.get("feature_version") != FEATURE_VERSION
            or feature.get("distance_method") != METHOD
        ):
            raise ValueError("Incompatible point features")
        by_id[identifier] = feature
    return by_id


def summarize_component(
    points: list[dict], features: dict, priority: str, prefs: Preferences, config: ScoringConfig
) -> dict:
    total_area = sum(p["weight_m2"] for p in points)
    distances, earned, known_area = [], 0.0, 0.0
    over_time_area = 0.0
    scale = (
        config.work_half_score_distance_m
        if priority == "work"
        else (config.half_score_distances_m.get(priority, PRIORITIES[priority][1]))
    )
    if priority == "work" and config.assumed_car_speed_kmh and prefs.work.max_minutes:
        scale = prefs.work.max_minutes / 60 * config.assumed_car_speed_kmh * 1000
    for point in points:
        if priority == "work":
            trip = commute(point, prefs.work, config)
            distance = trip["distance_m"]
            if trip["exceeds_time_with_tolerance"] is True:
                over_time_area += point["weight_m2"]
        else:
            distance, _ = infrastructure_component(features.get(point["id"], {}), priority)
        if distance is not None:
            weight = point["weight_m2"]
            distances.append((distance, weight))
            known_area += weight
            earned += weight * utility(distance, scale) * 100
    coverage = known_area / total_area
    lower = earned / total_area
    return {
        "priority": priority,
        "label": "Близость работы по прямой" if priority == "work" else PRIORITIES[priority][2],
        "score": lower if known_area else None,
        "score_upper_bound": lower + 100 * (1 - coverage),
        "coverage": coverage,
        "status": "available"
        if coverage >= 1 - 1e-10
        else "partial"
        if known_area
        else "missing_data",
        "half_score_distance_m": scale,
        "median_distance_m": weighted_quantile(distances, 0.5),
        "p90_distance_m": weighted_quantile(distances, 0.9),
        "residential_share_within_500m": sum(w for d, w in distances if d <= 500) / total_area,
        "residential_share_within_1000m": sum(w for d, w in distances if d <= 1000) / total_area,
        "share_beyond_time_tolerance": over_time_area / total_area
        if priority == "work" and config.assumed_car_speed_kmh and prefs.work.max_minutes
        else None,
        "explanation": "Среднее баллов жилых точек, взвешенное по площади; расстояния по прямой."
        if known_area
        else "Недостаточно данных для оценки.",
    }


def rank_districts(
    districts: list[dict],
    points: list[dict],
    features: list[dict],
    preferences: Preferences | dict,
    config: ScoringConfig | dict | None = None,
    *,
    apartment_result: dict | None = None,
    external_evidence: dict | None = None,
) -> dict:
    prefs = (
        preferences
        if isinstance(preferences, Preferences)
        else Preferences.model_validate(preferences)
    )
    cfg = (
        config if isinstance(config, ScoringConfig) else ScoringConfig.model_validate(config or {})
    )
    by_id = validate_points(districts, points, features)
    by_district = defaultdict(list)
    for point in points:
        by_district[point["district_id"]].append(point)
    weights, unsupported = resolved_weights(prefs)
    for item in unsupported:
        if item["priority"] == "ecology":
            item["reason"] = (
                "Измерения станций собраны, но покрытие жилой территории и качество архива ещё не подтверждены."
            )
        elif item["priority"] == "safety":
            item["reason"] = (
                "Есть исторические числа преступлений; нет согласованного населения, границ и проверенной сопоставимости."
            )
    total_weight = sum(weights.values())
    listings = defaultdict(list)
    if apartment_result is not None:
        if apartment_result["returned_count"] != apartment_result["eligible_count"]:
            raise ValueError("District listing counts require all eligible apartments, not top-N")
        for item in apartment_result["results"]:
            listings[item["apartment"]["district_name"]].append(item["apartment_id"])
    results = []
    for district in districts:
        if prefs.districts and district["district_name"] not in prefs.districts:
            continue
        selected = by_district[district["district_id"]]
        components = [summarize_component(selected, by_id, key, prefs, cfg) for key in weights]
        earned = known = upper = 0.0
        for component in components:
            weight = weights[component["priority"]]
            component["weight"] = weight
            earned += weight * (component["score"] or 0)
            upper += weight * component["score_upper_bound"]
            known += weight * component["coverage"]
            component["contribution_points"] = weight * (component["score"] or 0) / total_weight
        candidates = listings[district["district_name"]] if apartment_result is not None else None
        evidence = (external_evidence or {}).get(district["district_id"], {})
        results.append(
            {
                **district,
                "score": earned / total_weight if known else None,
                "score_upper_bound": upper / total_weight if total_weight else None,
                "score_coverage": known / total_weight if total_weight else 0.0,
                "scoring_status": "no_supported_priorities"
                if not weights
                else "unavailable"
                if not known
                else "complete"
                if known >= total_weight - 1e-10
                else "partial",
                "components": components,
                "external_evidence": evidence,
                "ecology_score": None,
                "safety_score": None,
                "matching_listing_count": len(candidates) if candidates is not None else None,
                "top_apartment_ids": candidates[:3] if candidates is not None else [],
                "listing_status": "not_evaluated"
                if candidates is None
                else "available"
                if candidates
                else "no_matching_listings",
                "warnings": WARNINGS,
            }
        )
    results.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0), r["district_id"]))
    for rank, row in enumerate(results, 1):
        row["rank"] = rank if weights and row["score"] is not None else None
    return {
        "scoring_version": VERSION,
        "status": "no_matching_districts"
        if not results
        else "ok"
        if weights
        else "no_supported_priorities",
        "preferences": prefs.model_dump(mode="json"),
        "config": cfg.model_dump(mode="json"),
        "effective_weights": weights,
        "unsupported_priorities": unsupported,
        "score_scale": [0, 100],
        "returned_count": len(results),
        "results": results,
        "commute": {
            "method": "straight_line",
            "is_routed": False,
            "assumed_car_speed_kmh": cfg.assumed_car_speed_kmh,
            "warning_threshold_minutes": prefs.work.max_minutes
            * (1 + cfg.commute_tolerance_fraction)
            if prefs.work and prefs.work.max_minutes
            else None,
            "limitation": "Минуты условные, только при явно заданной скорости; не прогноз поездки.",
        },
        "limitations": WARNINGS
        + [
            "Экология и безопасность пока не участвуют в сумме: сопоставимость данных не подтверждена.",
            "Нижняя/верхняя границы описывают пропуски, не статистический доверительный интервал.",
        ],
    }


def build(
    raw_dir: Path,
    output: Path,
    pois: Path,
    poi_metadata: Path,
    apartments: Path,
    buildings: Path | None = None,
    cell_size: int = 250,
) -> dict:
    paths = {
        "boundaries": raw_dir / "boundaries.json",
        "residential": raw_dir / "residential.json",
        "pois": pois,
        "poi_metadata": poi_metadata,
        "apartments": apartments,
    }
    if buildings:
        paths["buildings"] = buildings
    inputs = {key: {"path": str(path), "sha256": sha256(path)} for key, path in paths.items()}
    boundaries_payload = read_json(paths["boundaries"])
    residential_payload = read_json(paths["residential"])
    geojson = district_polygons(boundaries_payload)
    mask, geometry_report = residential_mask(
        residential_payload, read_json(buildings) if buildings else None
    )
    points, summaries = build_grid(geojson, mask, cell_size)
    snapshot_at = read_json(poi_metadata).get("timestamp_osm_base")
    if not snapshot_at:
        raise ValueError("POI snapshot date is required")
    feature_table, _, feature_report = calculate(
        pa.Table.from_pylist(points),
        pq.read_table(pois),
        snapshot_at=datetime.fromisoformat(snapshot_at),
    )
    feature_table = feature_table.rename_columns(
        ["point_id" if name == "apartment_id" else name for name in feature_table.column_names]
    )
    features = feature_table.to_pylist()
    defaults = rank_districts(
        summaries, points, features, {"priorities": {key: 1 for key in PRIORITIES}}
    )
    district_features = []
    for row in defaults["results"]:
        flat = {k: row[k] for k in summaries[0]}
        for component in row["components"]:
            for key in (
                "score",
                "coverage",
                "median_distance_m",
                "p90_distance_m",
                "residential_share_within_500m",
                "residential_share_within_1000m",
            ):
                flat[f"{component['priority']}_{key}"] = component[key]
        flat["poi_snapshot_at"] = snapshot_at
        district_features.append(flat)
    audit = audit_apartments(pq.read_table(apartments).to_pylist(), geojson, mask)
    output.mkdir(parents=True, exist_ok=True)
    # Mark incomplete before any mutation so a failed rebuild cannot expose mixed artifacts.
    write_json(output / "manifest.json", {"status": "building", "inputs": inputs})
    write_json(output / "districts.geojson", geojson)
    write_json(output / "district_summary.json", {"districts": summaries})
    write_parquet(output / "district_reference_points.parquet", points)
    write_parquet(output / "reference_point_features.parquet", features)
    write_parquet(output / "district_features.parquet", district_features)
    write_parquet(output / "apartment_district_audit.parquet", audit)
    outputs = {
        name: {"sha256": sha256(output / name)}
        for name in (
            "districts.geojson",
            "district_summary.json",
            "district_reference_points.parquet",
            "reference_point_features.parquet",
            "district_features.parquet",
            "apartment_district_audit.parquet",
        )
    }
    report = {
        "status": "complete",
        "version": VERSION,
        "computed_at": datetime.now(UTC).isoformat(),
        "inputs": inputs,
        "outputs": outputs,
        "district_count": len(summaries),
        "reference_points": len(points),
        "cell_size_m": cell_size,
        "metric_crs": "EPSG:32646",
        "weight_method": "mapped_residential_area_not_population",
        "poi_snapshot_at": snapshot_at,
        "boundary_snapshot_at": boundaries_payload.get("osm3s", {}).get("timestamp_osm_base"),
        "residential_snapshot_at": residential_payload.get("osm3s", {}).get("timestamp_osm_base"),
        "geometry_report": geometry_report,
        "apartment_audit": dict(Counter(r["status"] for r in audit)),
        "apartments_inside_residential_mask": sum(
            r["inside_mapped_residential_area"] is True for r in audit
        ),
        "warnings": WARNINGS + feature_report["warnings"],
    }
    write_json(output / "manifest.json", report)
    return report


def verified_manifest(directory: Path) -> dict:
    manifest = read_json(directory / "manifest.json")
    if manifest.get("status") != "complete" or manifest.get("version") != VERSION:
        raise ValueError("District build is incomplete or incompatible")
    for name, expected in manifest["outputs"].items():
        if sha256(directory / name) != expected["sha256"]:
            raise ValueError(f"District artifact checksum mismatch: {name}")
    return manifest


def recommend_from_files(
    directory: Path,
    apartments: Path,
    apartment_features: Path,
    apartment_report: Path,
    preferences: dict,
    config: dict | None = None,
) -> dict:
    manifest = verified_manifest(directory)
    apartment_manifest = read_json(apartment_report)
    if (
        apartment_manifest.get("status") != "complete"
        or sha256(apartments) != apartment_manifest["inputs"]["apartments"]["sha256"]
        or sha256(apartment_features)
        != apartment_manifest["outputs"]["apartment_features.parquet"]["sha256"]
        or sha256(apartments) != manifest["inputs"]["apartments"]["sha256"]
    ):
        raise ValueError("Apartment snapshots differ; rebuild features/district audit")
    audit = {
        r["apartment_id"]: r
        for r in pq.read_table(directory / "apartment_district_audit.parquet").to_pylist()
    }
    homes, unassigned = [], []
    for home in pq.read_table(apartments).to_pylist():
        assignment = audit[home["id"]]
        if assignment["spatial_district_id"] is None:
            unassigned.append(home["id"])
            continue
        # Original source data stays unchanged; district filtering here uses the spatial join.
        homes.append(home | {"district_name": assignment["spatial_district_name"]})
    if len(homes) > 1000:
        raise ValueError(
            "More than 1000 listings: extend apartment result pagination before aggregation"
        )
    apartment_result = recommend(
        homes,
        pq.read_table(apartment_features).to_pylist(),
        preferences,
        limit=max(1, len(homes)),
        config=config,
    )
    evidence_path = directory / "external_evidence.json"
    evidence = {}
    if evidence_path.exists():
        environment_manifest = read_json(directory / "environment_manifest.json")
        if environment_manifest.get("status") != "complete" or environment_manifest[
            "districts_sha256"
        ] != sha256(directory / "districts.geojson"):
            raise ValueError("Environmental evidence uses different boundaries; rebuild evidence")
        for name, digest in environment_manifest["outputs"].items():
            if sha256(directory / name) != digest:
                raise ValueError(f"Environmental evidence checksum mismatch: {name}")
        evidence = read_json(evidence_path)["districts"]
    result = rank_districts(
        read_json(directory / "district_summary.json")["districts"],
        pq.read_table(directory / "district_reference_points.parquet").to_pylist(),
        pq.read_table(directory / "reference_point_features.parquet").to_pylist(),
        preferences,
        config,
        apartment_result=apartment_result,
        external_evidence=evidence,
    )
    result["data_periods"] = {
        k: manifest[k]
        for k in ("poi_snapshot_at", "boundary_snapshot_at", "residential_snapshot_at")
    }
    result["unassigned_apartment_ids"] = unassigned
    result["listing_district_method"] = "spatial_join_to_versioned_osm_boundaries"
    result["computed_at"] = datetime.now(UTC).isoformat()
    result["district_manifest_sha256"] = sha256(directory / "manifest.json")
    result["environment_manifest_sha256"] = (
        sha256(directory / "environment_manifest.json") if evidence else None
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="District reference grid, features and recommendations"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--raw-dir", type=Path, default=Path("data/raw/districts"))
    collect.add_argument(
        "--overpass-url", default="https://maps.mail.ru/osm/tools/overpass/api/interpreter"
    )
    prepare = sub.add_parser("build")
    prepare.add_argument("--raw-dir", type=Path, default=Path("data/raw/districts"))
    prepare.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    prepare.add_argument("--pois", type=Path, default=Path("data/processed/geo_objects.parquet"))
    prepare.add_argument(
        "--poi-metadata", type=Path, default=Path("data/processed/geo_objects.metadata.json")
    )
    prepare.add_argument("--buildings", type=Path)
    prepare.add_argument("--cell-size", type=int, default=250)
    prepare.add_argument(
        "--apartments", type=Path, default=Path("data/processed/housing/apartments.parquet")
    )
    rank = sub.add_parser("recommend")
    rank.add_argument("--preferences", required=True, type=Path)
    rank.add_argument("--config", type=Path)
    rank.add_argument("--district-dir", type=Path, default=DEFAULT_OUTPUT)
    rank.add_argument(
        "--apartments", type=Path, default=Path("data/processed/housing/apartments.parquet")
    )
    rank.add_argument(
        "--apartment-features",
        type=Path,
        default=Path("data/processed/features/apartment_features.parquet"),
    )
    rank.add_argument(
        "--apartment-report", type=Path, default=Path("data/processed/features/feature_report.json")
    )
    rank.add_argument(
        "--output", type=Path, default=Path("data/processed/recommendations/districts.json")
    )
    args = parser.parse_args()
    if args.command == "collect":
        result = collect_geometry(args.raw_dir, Settings(overpass_url=args.overpass_url))
    elif args.command == "build":
        result = build(
            args.raw_dir,
            args.output_dir,
            args.pois,
            args.poi_metadata,
            args.apartments,
            args.buildings,
            args.cell_size,
        )
    else:
        result = recommend_from_files(
            args.district_dir,
            args.apartments,
            args.apartment_features,
            args.apartment_report,
            read_json(args.preferences),
            read_json(args.config) if args.config else None,
        )
        write_json(args.output, result)
    print(
        json.dumps(
            {
                k: result[k]
                for k in ("status", "district_count", "reference_points", "returned_count")
                if k in result
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
