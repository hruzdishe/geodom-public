from typing import Annotated

from fastapi import Depends

from geodom_backend.apartments.photo_presenter import (
    ApartmentPhotoPresenter,
)
from geodom_backend.apartments.presenter import (
    ApartmentPresenter,
)
from geodom_backend.storage.dependencies import (
    ObjectStorageDep,
)


def get_apartment_photo_presenter(
    storage: ObjectStorageDep,
) -> ApartmentPhotoPresenter:
    return ApartmentPhotoPresenter(
        storage
    )


ApartmentPhotoPresenterDep = Annotated[
    ApartmentPhotoPresenter,
    Depends(
        get_apartment_photo_presenter
    ),
]


def get_apartment_presenter(
    photos: ApartmentPhotoPresenterDep,
) -> ApartmentPresenter:
    return ApartmentPresenter(
        photos
    )


ApartmentPresenterDep = Annotated[
    ApartmentPresenter,
    Depends(
        get_apartment_presenter
    ),
]
