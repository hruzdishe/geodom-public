import logging

from geodom_backend.apartments.schemas import (
    ApartmentPhotoResponse,
)
from geodom_backend.db.models import (
    ApartmentPhoto,
)
from geodom_backend.storage.exceptions import (
    ObjectStorageError,
)
from geodom_backend.storage.provider import (
    ObjectStorage,
)

logger = logging.getLogger(__name__)


class ApartmentPhotoPresenter:
    def __init__(
        self,
        storage: ObjectStorage,
    ) -> None:
        self._storage = storage

    async def build(
        self,
        photos: list[ApartmentPhoto],
        *,
        public_only: bool,
    ) -> list[ApartmentPhotoResponse]:
        result: list[
            ApartmentPhotoResponse
        ] = []

        for photo in sorted(
            photos,
            key=lambda item: item.position,
        ):
            if (
                public_only
                and not photo.publication_allowed
            ):
                continue

            url: str | None = None

            try:
                url = (
                    await self._storage
                    .get_presigned_url(
                        bucket=photo.bucket,
                        key=photo.storage_key,
                    )
                )

            except ObjectStorageError:
                logger.exception(
                    "Failed to create URL for "
                    "photo %s",
                    photo.id,
                )

            result.append(
                ApartmentPhotoResponse(
                    id=photo.id,
                    position=photo.position,
                    is_cover=photo.is_cover,
                    width=photo.width,
                    height=photo.height,
                    mime_type=photo.mime_type,
                    size_bytes=photo.size_bytes,
                    url=url,
                )
            )

        return result
