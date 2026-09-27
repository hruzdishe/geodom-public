from typing import Protocol

class ObjectStorage(Protocol):
    async def ensure_bucket(self, bucket: str):
        ...

    async def upload(self, *, bucket: str, key: str, data: bytes, content_type: str):
        ...

    async def delete(self, *, bucket: str, key: str):
        ...

    async def exists(self, *, bucket: str, key: str) -> bool:
        ...

    async def get_presigned_url(self, *, bucket: str, key: str, expires_seconds: int | None = None) -> str:
        ...
