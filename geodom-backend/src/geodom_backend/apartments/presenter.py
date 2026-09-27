from geodom_backend.apartments.photo_presenter import (
    ApartmentPhotoPresenter,
)
from geodom_backend.apartments.schemas import (
    ApartmentDetailResponse,
    ApartmentResponse,
)
from geodom_backend.db.models import (
    Apartment,
)


class ApartmentPresenter:
    def __init__(
        self,
        photos: ApartmentPhotoPresenter,
    ) -> None:
        self._photos = photos

    async def response(
        self,
        apartment: Apartment,
        *,
        public_only: bool = True,
    ) -> ApartmentResponse:
        response = (
            ApartmentResponse.model_validate(
                apartment
            )
        )

        photos = await self._photos.build(
            list(apartment.photos),
            public_only=public_only,
        )

        return response.model_copy(
            update={
                "photos": photos,
            }
        )

    async def detail(
        self,
        apartment: Apartment,
        *,
        public_only: bool = True,
    ) -> ApartmentDetailResponse:
        response = (
            ApartmentDetailResponse
            .model_validate(
                apartment
            )
        )

        photos = await self._photos.build(
            list(apartment.photos),
            public_only=public_only,
        )

        return response.model_copy(
            update={
                "photos": photos,
            }
        )
