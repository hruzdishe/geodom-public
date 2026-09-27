from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from geodom_backend.db.models import ApartmentPhoto

class ApartmentPhotoRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def add_imported(self, photo: ApartmentPhoto) -> ApartmentPhoto:
        self._session.add(photo)
        await self._session.flush()
        return photo

    async def get_by_id(self, *, apartment_id: int, photo_id: int) -> ApartmentPhoto | None:
        statement = select(ApartmentPhoto).where(
            ApartmentPhoto.id == photo_id,
            ApartmentPhoto.apartment_id == apartment_id
        )

        result = await self._session.execute(statement)

        return result.scalar_one_or_none()

    async def get_all(self, apartment_id: int) -> list[ApartmentPhoto]:
        statement = (
            select(ApartmentPhoto)
            .where(ApartmentPhoto.apartment_id == apartment_id)
            .order_by(ApartmentPhoto.position)
        )

        result = await self._session.execute(statement)

        return list(result.scalars().all())

    async def count(self, apartment_id: int) -> int:
        statement = select(
            func.count(ApartmentPhoto.id)
        ).where(
            ApartmentPhoto.apartment_id == apartment_id
        )

        result = await self._session.execute(statement)

        return result.scalar_one()

    async def next_position(self, apartment_id: int) -> int:
        statement = select(
            func.coalesce(
                func.max(ApartmentPhoto.position),
                -1
            )
        ).where(ApartmentPhoto.apartment_id == apartment_id)

        result = await self._session.execute(statement)

        return result.scalar_one() + 1

    async def create_user_photo(
        self,
        *,
        apartment_id: int,
        bucket: str,
        storage_key: str,
        position: int,
        is_cover: bool,
        width: int,
        height: int,
        mime_type: str,
        size_bytes: int,
        sha256: str
    ) -> ApartmentPhoto:
        photo = ApartmentPhoto(
            apartment_id=apartment_id,
            bucket=bucket,
            storage_key=storage_key,
            local_path=None,
            source="user",
            source_url=None,
            listing_url=None,
            position=position,
            is_cover=is_cover,
            width=width,
            height=height,
            mime_type=mime_type,
            size_bytes=size_bytes,
            sha256=sha256,
            original_sha256=sha256,
            rights_status="user_uploaded",
            attribution=None,
            publication_allowed=True,
            image_kind="photo"
        )

        self._session.add(photo)

        await self._session.flush()

        return photo

    async def clear_cover(self, apartment_id: int):
        statement = (
            update(ApartmentPhoto)
            .where(
                ApartmentPhoto.apartment_id == apartment_id,
                ApartmentPhoto.is_cover.is_(True)
            )
            .values(
                is_cover=False
            )
        )

        await self._session.execute(statement)
        await self._session.flush()

    async def set_cover(self, *, apartment_id: int, photo: ApartmentPhoto):
        await self.clear_cover(apartment_id)

        photo.is_cover = True

        await self._session.flush()

    async def delete(self, photo: ApartmentPhoto):
        await self._session.delete(photo)
        await self._session.flush()

    async def reorder(self, *, apartment_id: int, photo_ids: list[int]) -> list[ApartmentPhoto]:
        photos = await self.get_all(apartment_id)
        existing_ids = {photo.id for photo in photos}
        requested_ids = set(photo_ids)

        if existing_ids != requested_ids or len(photo_ids) != len(requested_ids):
            raise ValueError(
                "photo_ids must contain every apartment photo exactly once"
            )

        statement = (
            update(ApartmentPhoto)
            .where(ApartmentPhoto.apartment_id == apartment_id)
            .values(position=ApartmentPhoto.position + 1000)
        )

        await self._session.execute(statement)
        await self._session.flush()

        for position, photo_id in enumerate(photo_ids):
            statement = (
                update(ApartmentPhoto)
                .where(
                    ApartmentPhoto.id == photo_id,
                    ApartmentPhoto.apartment_id == apartment_id
                )
                .values(position=position)
            )

            await self._session.execute(statement)

        await self._session.flush()

        return await self.get_all(apartment_id)
