"""Public PM2.5 archive and historical crime evidence; no fabricated district ratings."""

import argparse
import calendar
import hashlib
import json
import math
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import mean, median

import httpx
from shapely.geometry import Point, shape

from .district_geometry import sha256, write_parquet
from .pipeline import atomic_bytes, write_json

API = "https://air.krasn.ru/api/2.0"
SOURCE = "https://air.krasn.ru/help.html"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def get_archive(client: httpx.Client, path: Path, url: str, params: dict) -> dict:
    metadata_path = path.with_suffix(".metadata.json")
    if path.exists() and metadata_path.exists():
        metadata = read_json(metadata_path)
        if (
            metadata["sha256"] != sha256(path)
            or metadata["url"] != url
            or metadata["params"] != params
        ):
            raise ValueError(f"Archive cache mismatch: {path}")
        result = read_json(path)
    else:
        response = client.get(url, params=params)
        response.raise_for_status()
        result = response.json()
        if result.get("status", {}).get("code", -1) < 0:
            raise ValueError(f"Air API error: {result.get('status')}")
        atomic_bytes(path, response.content)
        write_json(
            metadata_path,
            {
                "url": url,
                "params": params,
                "sha256": hashlib.sha256(response.content).hexdigest(),
                "retrieved_at": datetime.now(UTC).isoformat(),
                "source_documentation": SOURCE,
                "attribution": "air.krasn.ru; Krasnoyarsk Scientific Center SB RAS",
            },
        )
    if result.get("status", {}).get("code", -1) < 0 or "data" not in result:
        raise ValueError("Incomplete air API response")
    return result


def collect_air(raw_dir: Path, year: int = 2025, project: int = 9) -> dict:
    if not 2019 <= year < datetime.now(UTC).year:
        raise ValueError("Choose a completed year from 2019 onwards")
    root = raw_dir / str(year) / str(project)
    with httpx.Client(timeout=60, headers={"User-Agent": "krasnoyarsk-ml/0.1 research"}) as client:
        catalog = get_archive(client, root / "catalog.json", f"{API}/projects/{project}", {})
        if not catalog["data"].get("sites"):
            raise ValueError("Empty air station catalog")
        for month in range(1, 13):
            start = date(year, month, 1)
            end = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
            get_archive(
                client,
                root / f"{month:02d}.json",
                f"{API}/data",
                {
                    "time_begin": f"{start.isoformat()} 00:00:00",
                    "time_end": f"{end.isoformat()} 00:00:00",
                    "time_interval": "day",
                    "projects": str(project),
                },
            )
    return {"status": "collected", "year": year, "project": project, "path": str(root)}


def normalize_air(catalog: dict, monthly: list[dict], year: int) -> tuple[list, list, dict]:
    sites = {int(s["id"]): s for s in catalog["data"]["sites"]}
    seen, rejected, duplicates = {}, [], 0
    for payload in monthly:
        if payload.get("status", {}).get("code", -1) < 0 or not isinstance(
            payload.get("data"), list
        ):
            raise ValueError("Invalid monthly air response")
        for value in payload["data"]:
            day = date.fromisoformat(value["time"][:10])
            if day.year != year:
                # API end-date semantics may include the next boundary day.
                continue
            site = int(value["site"])
            pm = value.get("pm25")
            if (
                site not in sites
                or isinstance(pm, bool)
                or not isinstance(pm, (int, float))
                or not math.isfinite(pm)
                or pm < 0
            ):
                rejected.append(
                    {
                        "station_id": site,
                        "date": day.isoformat(),
                        "reason": "unknown_station_or_invalid_pm25",
                    }
                )
                continue
            key = (site, day)
            if key in seen:
                if seen[key] != float(pm):
                    raise ValueError(f"Conflicting duplicate PM2.5 value: {key}")
                duplicates += 1
                continue
            seen[key] = float(pm)
    observations, grouped = [], defaultdict(list)
    for (site, day), value in sorted(seen.items()):
        station = sites[site]
        closed = station.get("end_date")
        before = station.get("begin_date")
        conflict = bool(
            (closed and day > date.fromisoformat(closed[:10]))
            or (before and day < date.fromisoformat(before[:10]))
        )
        row = {
            "station_id": str(site),
            "date": day.isoformat(),
            "pm25_ug_m3": value,
            "aggregation": "provider_daily",
            "source_timezone": "not_documented_by_response",
            "valid_hour_count": None,
            "hourly_completeness_verified": False,
            "catalog_activity_conflict": conflict,
            "source_url": f"{API}/data",
        }
        observations.append(row)
        grouped[site].append(row)
    total_days = 366 if calendar.isleap(year) else 365
    summaries = []
    for site, station in sorted(sites.items()):
        rows = grouped[site]
        values = sorted(r["pm25_ug_m3"] for r in rows)
        seasonal = {}
        for name, months in {
            "winter": {12, 1, 2},
            "spring": {3, 4, 5},
            "summer": {6, 7, 8},
            "autumn": {9, 10, 11},
        }.items():
            subset = [r["pm25_ug_m3"] for r in rows if int(r["date"][5:7]) in months]
            seasonal[name] = {
                "observed_days": len(subset),
                "mean_pm25_ug_m3": mean(subset) if subset else None,
            }
        summaries.append(
            {
                "station_id": str(site),
                "name": station["name"],
                "lat": station.get("geom_y"),
                "lon": station.get("geom_x"),
                "period_start": f"{year}-01-01",
                "period_end": f"{year}-12-31",
                "observed_days": len(rows),
                "day_coverage": len(rows) / total_days,
                "observed_daily_mean_pm25_ug_m3": mean(values) if values else None,
                "daily_p90_pm25_ug_m3": values[math.ceil(len(values) * 0.9) - 1]
                if values
                else None,
                "catalog_activity_conflict_days": sum(r["catalog_activity_conflict"] for r in rows),
                "seasons": seasonal,
                "hourly_completeness_verified": False,
                "historical_station_location_verified": False,
                "status": "provisional_observations" if rows else "no_data",
            }
        )
    return (
        observations,
        summaries,
        {
            "observations": len(observations),
            "stations_with_data": sum(s["observed_days"] > 0 for s in summaries),
            "deduplicated_boundary_days": duplicates,
            "rejected": rejected,
            "unit_basis": "pm25 field is ug/m3 per air.krasn.ru help and public client; AQI/PDK unused",
            "limitations": [
                "Daily aggregates do not expose hourly completeness or instrument quality flags.",
                "Catalog validity dates can disagree with returned historical observations.",
                "Historical station coordinates and API timezone require verification.",
                "Unvalidated spatial interpolation and rating thresholds are not applied.",
            ],
        },
    )


def build_evidence(
    raw_air: Path, districts: Path, crime: Path, output: Path, year: int = 2025
) -> dict:
    paths = [raw_air / "catalog.json"] + [raw_air / f"{m:02d}.json" for m in range(1, 13)]
    for path in paths:
        meta = read_json(path.with_suffix(".metadata.json"))
        if sha256(path) != meta["sha256"]:
            raise ValueError(f"Air archive checksum mismatch: {path}")
    observations, stations, report = normalize_air(
        read_json(paths[0]), [read_json(p) for p in paths[1:]], year
    )
    if not observations:
        raise ValueError("No valid PM2.5 observations in requested year; check archive and --year")
    polygons = read_json(districts)["features"]
    crime_data = read_json(crime)
    by_name = {r["district_name"]: r for r in crime_data["districts"]}
    evidence = {}
    for feature in polygons:
        props = feature["properties"]
        polygon = shape(feature["geometry"])
        local = [
            s
            for s in stations
            if s["lat"] is not None
            and s["lon"] is not None
            and polygon.covers(Point(s["lon"], s["lat"]))
        ]
        # Station summaries are context only, never area-wide exposure estimates.
        local_means = [s["observed_daily_mean_pm25_ug_m3"] for s in local if s["observed_days"]]
        history = by_name.get(props["district_name"], {})
        evidence[props["district_id"]] = {
            "air": {
                "status": "provisional_station_observations",
                "score": None,
                "source_url": SOURCE,
                "period_start": f"{year}-01-01",
                "period_end": f"{year}-12-31",
                "station_ids": [s["station_id"] for s in local],
                "stations_with_observations": len(local_means),
                "median_of_station_observed_means_pm25_ug_m3": median(local_means)
                if local_means
                else None,
                "spatial_coverage_verified": False,
                "reason": "Сводка станций, не средняя экспозиция жилой территории; полнота часов и исторические координаты не проверены.",
            },
            "safety": {
                "status": "insufficient_comparable_data",
                "score": None,
                "source_url": crime_data["source_url"],
                "period_start": crime_data["period_start"],
                "period_end": crime_data["period_end"],
                "registered_crimes": history.get("registered_crimes"),
                "population": None,
                "crimes_per_10000": None,
                "city_minus_district_sum": crime_data["city_minus_district_sum"],
                "boundary_compatible": False,
                "reason": "Нет согласованного населения и границ за период; расхождение суммы районов с городом не объяснено.",
            },
        }
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "environment_manifest.json", {"status": "building"})
    write_parquet(output / "air_observations.parquet", observations)
    write_json(output / "air_station_summary.json", {"stations": stations})
    report.update(
        {
            "year": year,
            "status": "provisional",
            "inputs": {str(p): sha256(p) for p in paths + [districts, crime]},
        }
    )
    write_json(output / "environment_report.json", report)
    write_json(
        output / "external_evidence.json",
        {"districts": evidence, "report": "environment_report.json"},
    )
    write_json(
        output / "environment_manifest.json",
        {
            "status": "complete",
            "districts_sha256": sha256(districts),
            "outputs": {
                name: sha256(output / name)
                for name in (
                    "air_observations.parquet",
                    "air_station_summary.json",
                    "environment_report.json",
                    "external_evidence.json",
                )
            },
        },
    )
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Collect and audit district environmental evidence"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect-air")
    collect.add_argument("--year", type=int, default=2025)
    collect.add_argument("--project", type=int, default=9)
    collect.add_argument("--raw-dir", type=Path, default=Path("data/raw/air"))
    prepare = sub.add_parser("build")
    prepare.add_argument("--year", type=int, default=2025)
    prepare.add_argument("--raw-air", type=Path, default=Path("data/raw/air/2025/9"))
    prepare.add_argument(
        "--districts", type=Path, default=Path("data/processed/districts/districts.geojson")
    )
    prepare.add_argument(
        "--crime", type=Path, default=Path("data/research/districts/crime_2024_official.json")
    )
    prepare.add_argument("--output-dir", type=Path, default=Path("data/processed/districts"))
    args = parser.parse_args()
    if args.command == "collect-air":
        result = collect_air(args.raw_dir, args.year, args.project)
    else:
        result = build_evidence(
            args.raw_air, args.districts, args.crime, args.output_dir, args.year
        )
    print(
        json.dumps(
            {
                k: result[k]
                for k in ("status", "year", "observations", "stations_with_data")
                if k in result
            }
        )
    )


if __name__ == "__main__":
    main()
