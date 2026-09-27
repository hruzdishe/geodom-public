"""Restore S3 objects referenced by an imported DB from the local media archive."""
import asyncio
import hashlib
from pathlib import Path

from sqlalchemy import select
from geodom_backend.db.models import ApartmentPhoto
from geodom_backend.db.session import session_factory, dispose_engine
from geodom_backend.storage.dependencies import get_object_storage

async def main():
    root=Path.cwd().resolve()
    storage=get_object_storage()
    uploaded=0
    try:
        async with session_factory() as session:
            photos=list((await session.scalars(select(ApartmentPhoto).order_by(ApartmentPhoto.id))).all())
            for index,photo in enumerate(photos,1):
                if await storage.exists(bucket=photo.bucket,key=photo.storage_key):
                    continue
                if not photo.local_path:
                    raise ValueError(f'Photo {photo.id} has no archive path; restore it from its storage backup')
                path=(root/photo.local_path).resolve()
                if not path.is_relative_to(root/'media'):
                    raise ValueError(f'Invalid archive path for photo {photo.id}')
                data=path.read_bytes()
                if photo.sha256 and hashlib.sha256(data).hexdigest()!=photo.sha256:
                    raise ValueError(f'Checksum mismatch for photo {photo.id}')
                await storage.upload(bucket=photo.bucket,key=photo.storage_key,data=data,content_type=photo.mime_type)
                uploaded+=1
                if index%100==0:
                    print(f'Restored {index}/{len(photos)}',flush=True)
            print(f'Photos checked: {len(photos)}; uploaded: {uploaded}',flush=True)
    finally:
        await dispose_engine()

if __name__=='__main__':
    asyncio.run(main())
