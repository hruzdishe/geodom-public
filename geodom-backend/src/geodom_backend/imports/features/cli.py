import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from geodom_backend.db.repositories import (
    ApartmentFeaturesRepository,
    ApartmentRepository,
)
from geodom_backend.db.session import (
    dispose_engine,
    session_factory,
)

from .reader import ApartmentFeatureReader
from .service import ApartmentFeatureImportService


async def run_import(
    *,
    features_dir: Path,
):
    parquet_path = (
        features_dir
        / "apartment_features.parquet"
    )

    report_path = (
        features_dir
        / "feature_report.json"
    )

    reader = ApartmentFeatureReader(
        parquet_path=parquet_path,
        report_path=report_path,
    )

    snapshot = reader.read()

    try:
        async with session_factory() as session:
            service = ApartmentFeatureImportService(
                session=session,
                apartments=ApartmentRepository(
                    session
                ),
                features=ApartmentFeaturesRepository(
                    session
                ),
            )

            return await service.import_snapshot(
                snapshot
            )

    finally:
        await dispose_engine()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Import apartment infrastructure "
            "features into GeoDom"
        )
    )

    parser.add_argument(
        "features_dir",
        type=Path,
        help=(
            "Directory containing "
            "apartment_features.parquet "
            "and feature_report.json"
        ),
    )

    args = parser.parse_args()

    report = asyncio.run(
        run_import(
            features_dir=(
                args.features_dir
                .expanduser()
                .resolve()
            )
        )
    )

    print(
        json.dumps(
            asdict(report),
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
