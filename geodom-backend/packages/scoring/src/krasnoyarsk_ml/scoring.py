"""Explainable preference scoring of apartments; no trained model or routed travel times."""

import argparse
import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

import pyarrow.parquet as pq
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .features import GEOD, METHOD
from .features import VERSION as FEATURES_VERSION
from .pipeline import write_json

VERSION = "apartment_scoring_v1"
Weight = Annotated[int, Field(strict=True, ge=0, le=5)]
PRIORITIES = {
    "schools": (("school",), 500, "Близость школ"),
    "kindergartens": (("kindergarten",), 400, "Близость детских садов"),
    "parks": (("park",), 700, "Близость парков"),
    "transport": (("public_transport",), 400, "Близость остановок"),
    "sport": (("sports_centre", "fitness_centre"), 1500, "Близость спортивных объектов"),
    "shopping_centers": (("mall",), 2000, "Близость торговых центров"),
    "supermarkets": (("supermarket",), 500, "Близость супермаркетов"),
    "healthcare": (("hospital", "clinic"), 1500, "Близость медицинских объектов"),
    "pharmacies": (("pharmacy",), 500, "Близость аптек"),
}
UNSUPPORTED = {
    "ecology": "Нет данных о качестве воздуха, шуме и других экологических показателях.",
    "safety": "Нет проверенных данных для оценки безопасности.",
    "cafes": "Кафе и рестораны ещё не включены в набор инфраструктуры.",
}


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class WorkLocation(RequestModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    max_minutes: float | None = Field(default=None, gt=0, le=1440)


class Preferences(RequestModel):
    price_min: int | None = Field(default=None, ge=0, strict=True)
    price_max: int | None = Field(default=None, ge=0, strict=True)
    rooms: list[Annotated[int, Field(strict=True, ge=0, le=20)]] = Field(default_factory=list)
    districts: list[str] = Field(default_factory=list)
    offer_type: Literal["sale", "rent"] = "sale"
    children_age_groups: list[Literal["preschool", "school"]] = Field(default_factory=list)
    priorities: dict[str, Weight] = Field(default_factory=dict)
    work: WorkLocation | None = None

    @model_validator(mode="after")
    def validate_request(self):
        if (
            self.price_min is not None
            and self.price_max is not None
            and self.price_min > self.price_max
        ):
            raise ValueError("price_min exceeds price_max")
        unknown = set(self.priorities) - (set(PRIORITIES) | set(UNSUPPORTED) | {"work"})
        if unknown:
            raise ValueError(f"Unknown priority keys: {sorted(unknown)}")
        return self


class ScoringConfig(RequestModel):
    # Null means distances only. A backend can explicitly enable hypothetical time estimation.
    assumed_car_speed_kmh: float | None = Field(default=None, gt=0, le=200)
    enforce_max_commute: bool = False
    commute_tolerance_fraction: float = Field(default=0.15, ge=0, le=1)
    work_half_score_distance_m: float = Field(default=5000, gt=0)
    half_score_distances_m: dict[str, Annotated[float, Field(gt=0, allow_inf_nan=False)]] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def known_scales(self):
        if unknown := set(self.half_score_distances_m) - set(PRIORITIES):
            raise ValueError(f"Unknown scale keys: {sorted(unknown)}")
        return self


def resolved_weights(prefs: Preferences) -> tuple[dict, list]:
    weights = {}
    if "preschool" in prefs.children_age_groups:
        weights["kindergartens"] = 5
    if "school" in prefs.children_age_groups:
        weights["schools"] = 5
    if prefs.work is not None:
        weights["work"] = 5
    weights.update(prefs.priorities)  # An explicit zero disables an automatic family/work weight.
    unavailable = [
        {"priority": key, "requested_weight": value, "reason": UNSUPPORTED[key]}
        for key, value in sorted(weights.items())
        if key in UNSUPPORTED and value > 0
    ]
    if weights.get("work", 0) > 0 and prefs.work is None:
        unavailable.append(
            {
                "priority": "work",
                "requested_weight": weights["work"],
                "reason": "Не заданы координаты работы.",
            }
        )
    return {
        k: v
        for k, v in sorted(weights.items())
        if v > 0 and k not in UNSUPPORTED and (k != "work" or prefs.work is not None)
    }, unavailable


def utility(distance: float, half_score_distance: float) -> float:
    return 1 / (1 + (distance / half_score_distance) ** 2)


def finite_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def coordinates(row: dict) -> bool:
    return all(
        finite_number(row.get(k)) and abs(row[k]) <= maximum
        for k, maximum in (("lat", 90), ("lon", 180))
    )


def commute(home: dict, work: WorkLocation | None, config: ScoringConfig) -> dict | None:
    if work is None:
        return None
    result = {
        "mode": "car",
        "method": "straight_line",
        "is_routed": False,
        "distance_m": None,
        "estimated_minutes": None,
        "assumed_speed_kmh": config.assumed_car_speed_kmh,
        "desired_max_minutes": work.max_minutes,
        "tolerance_fraction": config.commute_tolerance_fraction,
        "warning_threshold_minutes": work.max_minutes * (1 + config.commute_tolerance_fraction)
        if work.max_minutes
        else None,
        "exceeds_desired_time": None,
        "exceeds_time_with_tolerance": None,
        "status": "unavailable",
        "badge": None,
        "limitation": "Расстояние по прямой; дороги, мосты, пробки и время парковки не учитываются.",
    }
    if not coordinates(home):
        result["badge"] = "Не удалось оценить расстояние до работы"
        return result
    d = GEOD.inv(home["lon"], home["lat"], work.lon, work.lat)[2]
    result["distance_m"] = round(d, 3)
    result["status"] = "distance_only"
    if config.assumed_car_speed_kmh is not None:
        minutes = d / 1000 / config.assumed_car_speed_kmh * 60
        result["estimated_minutes"] = round(minutes, 2)
        result["status"] = "estimated_without_target"
        result["limitation"] += (
            f" Минуты — условная оценка при {config.assumed_car_speed_kmh:g} км/ч, не прогноз поездки."
        )
        if work.max_minutes is not None:
            exceeds = minutes > result["warning_threshold_minutes"] + 1e-9
            above_desired = minutes > work.max_minutes + 1e-9
            result.update(exceeds_desired_time=above_desired, exceeds_time_with_tolerance=exceeds)
            result["status"] = (
                "exceeds_tolerance"
                if exceeds
                else "within_tolerance"
                if above_desired
                else "within_target"
            )
            if exceeds:
                result["badge"] = (
                    "Условная оценка времени до работы выше желаемой с учётом люфта "
                    f"{config.commute_tolerance_fraction:.0%}"
                )
    elif work.max_minutes is not None:
        result["badge"] = "Время до работы не оценено — доступно только расстояние по прямой"
    return result


def infrastructure_component(feature: dict, priority: str) -> tuple[float | None, str | None]:
    groups = PRIORITIES[priority][0]
    measured = []
    for group in groups:
        distance = feature.get(f"{group}_nearest_distance_m")
        if (
            feature.get(f"{group}_observed_in_snapshot") is True
            and finite_number(distance)
            and distance >= 0
        ):
            measured.append((distance, feature.get(f"{group}_nearest_poi_id")))
    return min(measured, key=lambda x: (x[0], x[1] or "")) if measured else (None, None)


def recommend(
    apartments: list[dict],
    features: list[dict],
    preferences: Preferences | dict,
    limit: int = 10,
    config: ScoringConfig | dict | None = None,
) -> dict:
    prefs = (
        preferences
        if isinstance(preferences, Preferences)
        else Preferences.model_validate(preferences)
    )
    cfg = (
        config if isinstance(config, ScoringConfig) else ScoringConfig.model_validate(config or {})
    )
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("limit must be an integer in 1..1000")
    homes = {}
    for home in apartments:
        key = home.get("id")
        if not isinstance(key, str) or not key or key in homes:
            raise ValueError("Apartments must have unique nonempty string IDs")
        if not finite_number(home.get("price")) or home["price"] <= 0:
            raise ValueError(f"Invalid price: {key}")
        if type(home.get("rooms")) is not int or home["rooms"] < 0:
            raise ValueError(f"Invalid rooms: {key}")
        if home.get("currency") != "RUB":
            raise ValueError(f"Unsupported or missing currency: {key}")
        homes[key] = home
    by_id = {}
    for feature in features:
        key = feature.get("apartment_id")
        if not isinstance(key, str) or not key or key in by_id:
            raise ValueError("Features must have unique nonempty apartment IDs")
        if (
            feature.get("feature_version") != FEATURES_VERSION
            or feature.get("distance_method") != METHOD
        ):
            raise ValueError("Incompatible infrastructure features")
        by_id[key] = feature
    weights, unsupported = resolved_weights(prefs)
    total_weight = sum(weights.values())
    rejected = {key: 0 for key in ("price", "rooms", "district", "offer_type", "commute")}
    ranked, missing_feature_ids = [], []
    for identifier, home in sorted(homes.items()):
        failures = []
        if (prefs.price_min is not None and home["price"] < prefs.price_min) or (
            prefs.price_max is not None and home["price"] > prefs.price_max
        ):
            failures.append("price")
        if prefs.rooms and home["rooms"] not in prefs.rooms:
            failures.append("rooms")
        if prefs.districts and home.get("district_name") not in prefs.districts:
            failures.append("district")
        if home.get("offer_type") != prefs.offer_type:
            failures.append("offer_type")
        trip = commute(home, prefs.work, cfg)
        if cfg.enforce_max_commute and prefs.work and prefs.work.max_minutes is not None:
            if trip['estimated_minutes'] is None or trip['exceeds_desired_time']:
                failures.append('commute')
        if failures:
            for reason in failures:
                rejected[reason] += 1
            continue
        feature = by_id.get(identifier, {})
        if not feature:
            missing_feature_ids.append(identifier)
        components, earned, known_weight = [], 0.0, 0
        for priority, weight in weights.items():
            if priority == "work":
                distance, poi_id = trip["distance_m"], None
                scale = cfg.work_half_score_distance_m
                if cfg.assumed_car_speed_kmh is not None and prefs.work.max_minutes is not None:
                    scale = prefs.work.max_minutes / 60 * cfg.assumed_car_speed_kmh * 1000
                label = "Близость работы по прямой"
            else:
                distance, poi_id = infrastructure_component(feature, priority)
                scale = cfg.half_score_distances_m.get(priority, PRIORITIES[priority][1])
                label = PRIORITIES[priority][2]
            value = utility(distance, scale) if distance is not None else None
            contribution = weight * value if value is not None else 0.0
            earned += contribution
            if value is not None:
                known_weight += weight
            components.append(
                {
                    "priority": priority,
                    "label": label,
                    "weight": weight,
                    "distance_m": distance,
                    "nearest_poi_id": poi_id,
                    "half_score_distance_m": scale,
                    "score": round(value * 100, 4) if value is not None else None,
                    "contribution_points": round(100 * contribution / total_weight, 4),
                    "status": "available" if value is not None else "missing_data",
                    "explanation": f"{label}: примерно {round(distance)} м по прямой"
                    if distance is not None
                    else f"{label}: недостаточно данных",
                }
            )
        score = 100 * earned / total_weight if known_weight else None
        score_upper = (
            100 * (earned + total_weight - known_weight) / total_weight if total_weight else None
        )
        ranked.append(
            {
                "apartment_id": identifier,
                "score": round(score, 4) if score is not None else None,
                "score_upper_bound": round(score_upper, 4) if score_upper is not None else None,
                "score_coverage": round(known_weight / total_weight, 4) if total_weight else 0.0,
                "scoring_status": "complete"
                if known_weight and known_weight == total_weight
                else "partial"
                if known_weight
                else "unavailable",
                "components": components,
                "commute": trip,
                "poi_snapshot_at": (
                    feature["poi_snapshot_at"].isoformat()
                    if isinstance(feature.get("poi_snapshot_at"), datetime)
                    else feature.get("poi_snapshot_at")
                ),
                "apartment": {
                    key: home.get(key)
                    for key in (
                        "id",
                        "title",
                        "price",
                        "currency",
                        "rooms",
                        "area",
                        "floor",
                        "floors_total",
                        "address",
                        "district_name",
                        "lat",
                        "lon",
                        "cover_storage_key",
                        "photo_count",
                        "source_url",
                    )
                },
                "_sort_score": score,
            }
        )
    ranked.sort(
        key=lambda r: (r["_sort_score"] is None, -(r["_sort_score"] or 0), r["apartment_id"])
    )
    eligible = len(ranked)
    for rank, row in enumerate(ranked, 1):
        row["rank"] = rank
        del row["_sort_score"]
    return {
        "scoring_version": VERSION,
        "preferences": prefs.model_dump(mode="json"),
        "config": cfg.model_dump(mode="json"),
        "effective_weights": weights,
        "unsupported_priorities": unsupported,
        "total_apartments": len(homes),
        "eligible_count": eligible,
        "returned_count": min(limit, eligible),
        "filter_rejection_counts": rejected,
        "filter_rejection_counts_overlap": True,
        "missing_feature_ids": missing_feature_ids,
        "status": "no_matches"
        if not eligible
        else "no_supported_priorities"
        if not weights
        else "ok",
        "results": ranked[:limit],
        "limitations": [
            "Эвристический скоринг соответствия предпочтениям, не обученная ML-модель и не вероятность.",
            "Время на машине не рассчитано по дорожной сети; возможна только явно включённая условная оценка.",
            "OSM неполон, ближайшие точки могут быть центрами зданий/территорий; качество школ не оценено.",
            "При пропусках score — нижняя граница; неизвестные критерии не считаются подтверждённо плохими.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Explainable apartment preference scoring")
    parser.add_argument("--preferences", required=True, type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument(
        "--apartments", type=Path, default=Path("data/processed/housing/apartments.parquet")
    )
    parser.add_argument(
        "--features", type=Path, default=Path("data/processed/features/apartment_features.parquet")
    )
    parser.add_argument(
        "--feature-report", type=Path, default=Path("data/processed/features/feature_report.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/processed/recommendations/recommendations.json")
    )
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    # Fail on stale/mismatched joins instead of quietly combining different snapshots.
    report = json.loads(args.feature_report.read_text(encoding="utf-8"))
    if report.get("status") != "complete":
        raise ValueError("Feature computation is not complete")
    actual = hashlib.sha256(args.apartments.read_bytes()).hexdigest()
    if actual != report["inputs"]["apartments"]["sha256"]:
        raise ValueError("Apartments differ from feature input; recompute features first")
    if (
        hashlib.sha256(args.features.read_bytes()).hexdigest()
        != report["outputs"]["apartment_features.parquet"]["sha256"]
    ):
        raise ValueError("Feature checksum mismatch")
    output = recommend(
        pq.read_table(args.apartments).to_pylist(),
        pq.read_table(args.features).to_pylist(),
        json.loads(args.preferences.read_text(encoding="utf-8")),
        args.limit,
        json.loads(args.config.read_text(encoding="utf-8")) if args.config else None,
    )
    output["computed_at"] = datetime.now(UTC).isoformat()
    output["inputs"] = {
        "apartments_sha256": actual,
        "feature_version": report["feature_version"],
        "poi_snapshot_at": report["poi_snapshot_at"],
    }
    # Normalize source datetimes to JSON for direct API/CLI use.
    output = json.loads(json.dumps(output, ensure_ascii=False, default=lambda d: d.isoformat()))
    write_json(args.output, output)
    print(
        json.dumps(
            {
                k: output[k]
                for k in ("status", "eligible_count", "returned_count", "effective_weights")
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
