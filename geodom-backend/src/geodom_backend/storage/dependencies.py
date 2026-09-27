from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from geodom_backend.config import settings

from .minio import MinioObjectStorage
from .provider import ObjectStorage

@lru_cache
def get_object_storage() -> MinioObjectStorage:
    return MinioObjectStorage(
        endpoint=settings.storage_endpoint,
        access_key=settings.storage_access_key,
        secret_key=settings.storage_secret_key,
        secure=settings.storage_secure,
        default_presigned_ttl_seconds=settings.storage_presigned_ttl_seconds
    )

ObjectStorageDep = Annotated[
    ObjectStorage,
    Depends(get_object_storage)
]
