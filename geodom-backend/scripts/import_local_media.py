"""Import local archive photos into MinIO and attach them to existing apartments."""
import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from geodom_backend.db.session import dispose_engine, session_factory
from geodom_backend.imports.housing.media_service import HousingMediaImportService
from geodom_backend.storage.dependencies import get_object_storage


async def run(args):
    try:
        async with session_factory() as session:
            report = await HousingMediaImportService(session, get_object_storage()).import_directory(
                args.media_dir, bucket=args.bucket, allow_publication=args.allow_publication
            )
            print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    finally:
        await dispose_engine()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("media_dir", type=Path, nargs="?", default=Path("media"))
    parser.add_argument("--bucket", default="geodom-seed-media")
    parser.add_argument("--allow-publication", action="store_true", help="Explicitly authorize public display of these archive photos; default keeps them private")
    asyncio.run(run(parser.parse_args()))
