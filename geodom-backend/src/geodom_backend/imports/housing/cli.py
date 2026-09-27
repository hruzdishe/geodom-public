import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from geodom_backend.db.session import dispose_engine, session_factory
from geodom_backend.imports.housing.dependencies import create_housing_import_service
from geodom_backend.imports.housing.reader import HousingSnapshotReader

async def run_import(*, data_dir: Path, validate_files: bool):
    try:
        reader = HousingSnapshotReader(root=data_dir)

        snapshot=reader.read()

        async with session_factory() as session:
            service = create_housing_import_service(session)

            return await service.import_snapshot(snapshot, validate_files=validate_files)

    finally:
        await dispose_engine()

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import GeoDom housing snapshot into PostgreSQL"
    )

    parser.add_argument(
        "data_dir",
        type=Path,
        help="Dataset root containing processed/housing/"
    )

    parser.add_argument(
        "--validate-files",
        action="store_true",
        help="Also validate local media files and their SHA-256 hashes"
    )

    args = parser.parse_args()

    data_dir = args.data_dir.expanduser().resolve()

    report = asyncio.run(
        run_import(
            data_dir=data_dir,
            validate_files=args.validate_files
        )
    )

    print(
        json.dumps(
            asdict(report),
            ensure_ascii=False,
            indent=2
        )
    )

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
