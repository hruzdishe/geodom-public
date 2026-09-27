"""Reviewable PostgreSQL import and offline handoff. Does not connect to a server."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

import pyarrow.parquet as pq

from .district_geometry import sha256
from .districts import read_json, verified_manifest
from .pipeline import atomic_bytes, write_json


def sql_literal(value: str) -> str:
    # The generated transaction explicitly enables standard_conforming_strings.
    return "'" + value.replace("'", "''") + "'"


def export(directory: Path, output: Path, example: Path, readme: Path) -> dict:
    manifest = verified_manifest(directory)
    snapshot = sha256(directory / "manifest.json")
    environment = read_json(directory / "environment_manifest.json")
    if environment.get("status") != "complete" or environment["districts_sha256"] != sha256(
        directory / "districts.geojson"
    ):
        raise ValueError("Environment evidence must match exported boundaries")
    for name, digest in environment["outputs"].items():
        if sha256(directory / name) != digest:
            raise ValueError(f"Environment checksum mismatch: {name}")
    sample = read_json(example)
    if sample.get("district_manifest_sha256") != snapshot or sample.get(
        "environment_manifest_sha256"
    ) != sha256(directory / "environment_manifest.json"):
        raise ValueError("Example recommendations are stale; regenerate them")
    geo = read_json(directory / "districts.geojson")["features"]
    features = {
        r["district_id"]: r
        for r in pq.read_table(directory / "district_features.parquet").to_pylist()
    }
    evidence = read_json(directory / "external_evidence.json")["districts"]
    # Include evidence identity: refreshing measurements creates a new feature snapshot.
    snapshot = hashlib.sha256(
        (snapshot + sha256(directory / "environment_manifest.json")).encode()
    ).hexdigest()
    rows, statements = (
        [],
        [
            "BEGIN;",
            "SET LOCAL standard_conforming_strings = on;",
            "CREATE SCHEMA IF NOT EXISTS geodom_ml;",
            (
                "CREATE TABLE IF NOT EXISTS geodom_ml.district_versions ("
                "district_id text NOT NULL, boundary_version text NOT NULL, district_name text NOT NULL, "
                "geometry_geojson jsonb NOT NULL, properties jsonb NOT NULL, "
                "PRIMARY KEY (district_id, boundary_version));"
            ),
            (
                "CREATE TABLE IF NOT EXISTS geodom_ml.district_feature_snapshots ("
                "snapshot_id text NOT NULL, district_id text NOT NULL, boundary_version text NOT NULL, "
                "features jsonb NOT NULL, environmental_evidence jsonb NOT NULL, metadata jsonb NOT NULL, "
                "PRIMARY KEY (snapshot_id, district_id), FOREIGN KEY (district_id, boundary_version) "
                "REFERENCES geodom_ml.district_versions (district_id, boundary_version));"
            ),
        ],
    )
    metadata = {
        "district_manifest_sha256": sha256(directory / "manifest.json"),
        "environment_manifest_sha256": sha256(directory / "environment_manifest.json"),
        "computed_at": manifest["computed_at"],
        "scoring_version": manifest["version"],
        "attribution": "OpenStreetMap contributors, ODbL 1.0; air.krasn.ru; Krasnoyarsk Krai Prosecutor",
        "status": "provisional_mvp",
    }
    for item in geo:
        props = item["properties"]
        identifier, version = props["district_id"], props["boundary_version"]
        row = {
            "snapshot_id": snapshot,
            "district_id": identifier,
            "boundary_version": version,
            "district_name": props["district_name"],
            "geometry_geojson": item["geometry"],
            "properties": props,
            "features": features[identifier],
            "environmental_evidence": evidence[identifier],
            "metadata": metadata,
        }
        rows.append(row)

        def json_sql(value):
            return sql_literal(json.dumps(value, ensure_ascii=False)) + "::jsonb"

        statements.append(
            "INSERT INTO geodom_ml.district_versions "
            "(district_id, boundary_version, district_name, geometry_geojson, properties) VALUES ("
            + ", ".join(
                [
                    sql_literal(identifier),
                    sql_literal(version),
                    sql_literal(props["district_name"]),
                    json_sql(item["geometry"]),
                    json_sql(props),
                ]
            )
            + ") ON CONFLICT (district_id, boundary_version) DO UPDATE SET "
            "district_name=EXCLUDED.district_name, geometry_geojson=EXCLUDED.geometry_geojson, properties=EXCLUDED.properties;"
        )
        statements.append(
            "INSERT INTO geodom_ml.district_feature_snapshots "
            "(snapshot_id, district_id, boundary_version, features, environmental_evidence, metadata) VALUES ("
            + ", ".join(
                [
                    sql_literal(snapshot),
                    sql_literal(identifier),
                    sql_literal(version),
                    json_sql(features[identifier]),
                    json_sql(evidence[identifier]),
                    json_sql(metadata),
                ]
            )
            + ") ON CONFLICT (snapshot_id, district_id) DO NOTHING;"
        )
    statements.append("COMMIT;")
    output.mkdir(parents=True, exist_ok=True)
    atomic_bytes(
        output / "district_import.jsonl",
        ("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n").encode(),
    )
    atomic_bytes(output / "import_postgres.sql", ("\n".join(statements) + "\n").encode())
    names = [
        "districts.geojson",
        "district_features.parquet",
        "district_reference_points.parquet",
        "reference_point_features.parquet",
        "apartment_district_audit.parquet",
        "manifest.json",
        "environment_manifest.json",
        "external_evidence.json",
        "environment_report.json",
        "air_observations.parquet",
        "air_station_summary.json",
        "district_summary.json",
    ]
    for name in names:
        atomic_bytes(output / name, (directory / name).read_bytes())
    atomic_bytes(output / "districts_family.json", example.read_bytes())
    atomic_bytes(output / "README.md", readme.read_bytes())
    files = names + [
        "district_import.jsonl",
        "import_postgres.sql",
        "districts_family.json",
        "README.md",
    ]
    report = {
        "status": "complete",
        "districts": len(rows),
        "snapshot_id": snapshot,
        "files": {name: sha256(output / name) for name in files},
        "postgres_import_executed": False,
        "minio_upload_executed": False,
    }
    write_json(output / "export_manifest.json", report)
    archive = output.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in files + ["export_manifest.json"]:
            bundle.write(output / name, name)
    return report | {"archive": str(archive)}


def main():
    parser = argparse.ArgumentParser(description="Export district data and PostgreSQL import SQL")
    parser.add_argument("--district-dir", type=Path, default=Path("data/processed/districts"))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/exports/district_scoring_bundle")
    )
    parser.add_argument(
        "--example", type=Path, default=Path("data/processed/recommendations/districts_family.json")
    )
    parser.add_argument("--readme", type=Path, default=Path("DISTRICT_SCORING_README.md"))
    args = parser.parse_args()
    result = export(args.district_dir, args.output_dir, args.example, args.readme)
    print(json.dumps({k: result[k] for k in ("status", "districts", "archive")}))


if __name__ == "__main__":
    main()
