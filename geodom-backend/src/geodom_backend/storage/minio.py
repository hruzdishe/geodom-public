import asyncio
from datetime import timedelta
from io import BytesIO

from minio import Minio
from minio.error import S3Error

from geodom_backend.storage.exceptions import ObjectNotFoundError, ObjectStorageUnavailableError

class MinioObjectStorage:
    def __init__(self, *, endpoint: str, access_key: str, secret_key: str, secure: bool, default_presigned_ttl_seconds: int):
        self._client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )

        self._default_presigned_ttl_seconds = default_presigned_ttl_seconds

    async def ensure_bucket(self, bucket: str):
        try:
            await asyncio.to_thread(self._ensure_bucket_sync, bucket)
        except S3Error as e:
            raise ObjectStorageUnavailableError("Failed to ensure storage bucket") from e

    def _ensure_bucket_sync(self, bucket: str):
        if not self._client.bucket_exists(bucket):
            self._client.make_bucket(bucket)

    async def upload(self, *, bucket: str, key: str, data: bytes, content_type: str):
        try:
            await self.ensure_bucket(bucket)
            await asyncio.to_thread(self._upload_sync, bucket, key, data, content_type)
        except ObjectStorageUnavailableError: raise
        except S3Error as e:
            raise ObjectStorageUnavailableError(
                "Failed to upload object"
            ) from e

    def _upload_sync(self, bucket: str, key: str, data: bytes, content_type: str):
        stream = BytesIO(data)
        self._client.put_object(
            bucket_name=bucket,
            object_name=key,
            data=stream,
            length=len(data),
            content_type=content_type
        )

    async def delete(self, *, bucket: str, key: str):
        try:
            await asyncio.to_thread(self._client.remove_object, bucket, key)
        except S3Error as e:
            raise ObjectStorageUnavailableError("Failed to delete object") from e

    async def exists(self, *, bucket: str, key: str) -> bool:
        try:
            await asyncio.to_thread(
                self._client.stat_object, bucket, key
            )
        except S3Error as e:
            if e.code in {
                "NoSuchKey", "NoSuchObject", "NoSuchBucket", "XMinioInvalidObjectName"
            }:
                return False

            raise ObjectStorageUnavailableError("Failed to check object") from e

        return True

    async def get_presigned_url(self, *, bucket: str, key: str, expires_seconds: int | None = None) -> str:
        ttl = expires_seconds or self._default_presigned_ttl_seconds

        try:
            return await asyncio.to_thread(
                self._client.presigned_get_object,
                bucket,
                key,
                timedelta(seconds=ttl)
            )
        except S3Error as e:
            raise ObjectStorageUnavailableError(
                "Failed to generate presigned URL"
            ) from e
