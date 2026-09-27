import hashlib
import logging
from dataclasses import dataclass
from io import BytesIO
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from geodom_backend.storage.exceptions import ObjectStorageUnavailableError
from sqlalchemy.ext.asyncio import AsyncSession

from geodom_backend.apartments.enums import (
    ApartmentStatus,
)
from geodom_backend.apartments.exceptions import (
    ApartmentNotFoundError,
    ApartmentPermissionError,
)
from geodom_backend.apartments.photo_exceptions import (
    ApartmentPhotoLimitError,
    ApartmentPhotoNotFoundError,
    InvalidApartmentPhotoError,
    InvalidPhotoOrderError,
)
from geodom_backend.apartments.schemas import (
    ApartmentPhotoResponse,
)
from geodom_backend.config import settings
from geodom_backend.db.models import (
    Apartment,
    ApartmentPhoto,
    User,
)
from geodom_backend.db.repositories import (
    ApartmentPhotoRepository,
    ApartmentRepository,
)
from geodom_backend.storage.provider import (
    ObjectStorage,
)

logger = logging.getLogger(__name__)


@dataclass(
    frozen=True,
    slots=True,
)
class ValidatedImage:
    data: bytes

    width: int
    height: int

    mime_type: str
    extension: str

    sha256: str


class ApartmentPhotoService:
    _FORMAT_MAP = {
        "JPEG": (
            "image/jpeg",
            "jpg",
        ),
        "PNG": (
            "image/png",
            "png",
        ),
        "WEBP": (
            "image/webp",
            "webp",
        ),
    }

    def __init__(
        self,
        *,
        session: AsyncSession,
        apartments: ApartmentRepository,
        photos: ApartmentPhotoRepository,
        storage: ObjectStorage,
    ) -> None:
        self._session = session
        self._apartments = apartments
        self._photos = photos
        self._storage = storage

    async def upload(
        self,
        *,
        apartment_id: int,
        user: User,
        file: UploadFile,
        is_cover: bool,
    ) -> ApartmentPhotoResponse:
        await self._get_owned_apartment(
            apartment_id=apartment_id,
            user=user,
        )

        photo_count = await self._photos.count(
            apartment_id
        )

        if (
            photo_count
            >= settings.storage_max_photos_per_apartment
        ):
            raise ApartmentPhotoLimitError(
                "Maximum number of photos reached"
            )

        image = await self._validate_file(
            file
        )

        position = (
            await self._photos.next_position(
                apartment_id
            )
        )

        # Первое фото автоматически становится cover.
        make_cover = (
            is_cover
            or photo_count == 0
        )

        bucket = (
            settings.storage_user_bucket
        )

        storage_key = (
            f"apartments/{apartment_id}/"
            f"{uuid4().hex}."
            f"{image.extension}"
        )

        await self._storage.upload(
            bucket=bucket,
            key=storage_key,
            data=image.data,
            content_type=image.mime_type,
        )

        try:
            if make_cover:
                await self._photos.clear_cover(
                    apartment_id
                )

            photo = (
                await self._photos
                .create_user_photo(
                    apartment_id=apartment_id,
                    bucket=bucket,
                    storage_key=storage_key,
                    position=position,
                    is_cover=make_cover,
                    width=image.width,
                    height=image.height,
                    mime_type=image.mime_type,
                    size_bytes=len(
                        image.data
                    ),
                    sha256=image.sha256,
                )
            )

            await self._session.commit()

        except Exception:
            await self._session.rollback()

            try:
                await self._storage.delete(
                    bucket=bucket,
                    key=storage_key,
                )
            except Exception:
                logger.exception(
                    "Failed to cleanup uploaded "
                    "object %s/%s",
                    bucket,
                    storage_key,
                )

            raise

        return await self._to_response(
            photo
        )

    async def delete(
        self,
        *,
        apartment_id: int,
        photo_id: int,
        user: User,
    ) -> None:
        await self._get_owned_apartment(
            apartment_id=apartment_id,
            user=user,
        )

        photo = await self._get_photo(
            apartment_id=apartment_id,
            photo_id=photo_id,
        )

        bucket = photo.bucket
        storage_key = photo.storage_key
        was_cover = photo.is_cover

        try:
            await self._photos.delete(
                photo
            )

            if was_cover:
                remaining = (
                    await self._photos.get_all(
                        apartment_id
                    )
                )

                if remaining:
                    await self._photos.set_cover(
                        apartment_id=apartment_id,
                        photo=remaining[0],
                    )

            await self._normalize_positions(
                apartment_id
            )

            await self._session.commit()

        except Exception:
            await self._session.rollback()
            raise

        # Сначала фиксируем DB.
        # Если MinIO delete упадёт,
        # останется только orphan object,
        # но не сломанная ссылка в БД.
        try:
            await self._storage.delete(
                bucket=bucket,
                key=storage_key,
            )
        except Exception:
            logger.exception(
                "Failed to delete orphaned "
                "object %s/%s",
                bucket,
                storage_key,
            )

    async def set_cover(
        self,
        *,
        apartment_id: int,
        photo_id: int,
        user: User,
    ) -> ApartmentPhotoResponse:
        await self._get_owned_apartment(
            apartment_id=apartment_id,
            user=user,
        )

        photo = await self._get_photo(
            apartment_id=apartment_id,
            photo_id=photo_id,
        )

        try:
            await self._photos.set_cover(
                apartment_id=apartment_id,
                photo=photo,
            )

            await self._session.commit()

        except Exception:
            await self._session.rollback()
            raise

        return await self._to_response(
            photo
        )

    async def reorder(
        self,
        *,
        apartment_id: int,
        photo_ids: list[int],
        user: User,
    ) -> list[ApartmentPhotoResponse]:
        await self._get_owned_apartment(
            apartment_id=apartment_id,
            user=user,
        )

        try:
            try:
                photos = (
                    await self._photos.reorder(
                        apartment_id=apartment_id,
                        photo_ids=photo_ids,
                    )
                )

            except ValueError as exc:
                raise InvalidPhotoOrderError(
                    str(exc)
                ) from exc

            await self._session.commit()

        except Exception:
            await self._session.rollback()
            raise

        return [
            await self._to_response(
                photo
            )
            for photo in photos
        ]

    async def get_my_photos(
        self,
        *,
        apartment_id: int,
        user: User,
    ) -> list[ApartmentPhotoResponse]:
        await self._get_owned_apartment(
            apartment_id=apartment_id,
            user=user,
        )

        photos = await self._photos.get_all(
            apartment_id
        )

        return [
            await self._to_response(
                photo
            )
            for photo in photos
        ]

    async def _get_owned_apartment(
        self,
        *,
        apartment_id: int,
        user: User,
    ) -> Apartment:
        apartment = (
            await self._apartments.get_by_id(
                apartment_id
            )
        )

        if (
            apartment is None
            or apartment.status
            == ApartmentStatus.DELETED
        ):
            raise ApartmentNotFoundError

        if apartment.owner_id != user.id:
            raise ApartmentPermissionError

        return apartment

    async def _get_photo(
        self,
        *,
        apartment_id: int,
        photo_id: int,
    ) -> ApartmentPhoto:
        photo = await self._photos.get_by_id(
            apartment_id=apartment_id,
            photo_id=photo_id,
        )

        if photo is None:
            raise ApartmentPhotoNotFoundError

        return photo

    async def _validate_file(
        self,
        file: UploadFile,
    ) -> ValidatedImage:
        max_size = (
            settings.storage_max_photo_size_bytes
        )

        data = await file.read(
            max_size + 1
        )

        if not data:
            raise InvalidApartmentPhotoError(
                "Photo is empty"
            )

        if len(data) > max_size:
            raise InvalidApartmentPhotoError(
                "Photo is too large"
            )

        try:
            with Image.open(
                BytesIO(data)
            ) as image:
                image.verify()

            with Image.open(
                BytesIO(data)
            ) as image:
                image_format = image.format

                width, height = image.size

        except (
            UnidentifiedImageError,
            OSError,
        ) as exc:
            raise InvalidApartmentPhotoError(
                "Invalid image file"
            ) from exc

        if (
            image_format
            not in self._FORMAT_MAP
        ):
            raise InvalidApartmentPhotoError(
                "Only JPEG, PNG and WebP "
                "images are supported"
            )

        if width <= 0 or height <= 0:
            raise InvalidApartmentPhotoError(
                "Invalid image dimensions"
            )

        mime_type, extension = (
            self._FORMAT_MAP[
                image_format
            ]
        )

        return ValidatedImage(
            data=data,
            width=width,
            height=height,
            mime_type=mime_type,
            extension=extension,
            sha256=hashlib.sha256(
                data
            ).hexdigest(),
        )

    async def _normalize_positions(
        self,
        apartment_id: int,
    ) -> None:
        photos = await self._photos.get_all(
            apartment_id
        )

        if not photos:
            return

        photo_ids = [
            photo.id
            for photo in photos
        ]

        await self._photos.reorder(
            apartment_id=apartment_id,
            photo_ids=photo_ids,
        )

    async def _to_response(
        self,
        photo: ApartmentPhoto,
    ) -> ApartmentPhotoResponse:
        try:
            url = await self._storage.get_presigned_url(
                bucket=photo.bucket,
                key=photo.storage_key
            )
        except ObjectStorageUnavailableError:
            logger.warning(
                "Could not generate presigned URL for apartment photo %s",
                photo.id, exc_info=True
            )
            url = None

        return ApartmentPhotoResponse(
            id=photo.id,
            position=photo.position,
            is_cover=photo.is_cover,
            width=photo.width,
            height=photo.height,
            mime_type=photo.mime_type,
            size_bytes=photo.size_bytes,
            url=url,
        )
