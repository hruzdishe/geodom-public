from typing import Annotated

from fastapi import Depends

from geodom_backend.apartments.photo_service import (
    ApartmentPhotoService,
)
from geodom_backend.db import DatabaseSession
from geodom_backend.db.repositories import (
    ApartmentPhotoRepository,
    ApartmentRepository,
)
from geodom_backend.storage.dependencies import (
    ObjectStorageDep,
)


def get_apartment_photo_repository(
    session: DatabaseSession,
) -> ApartmentPhotoRepository:
    return ApartmentPhotoRepository(
        session
    )


ApartmentPhotoRepositoryDep = Annotated[
    ApartmentPhotoRepository,
    Depends(
        get_apartment_photo_repository
    ),
]


def get_photo_apartment_repository(
    session: DatabaseSession,
) -> ApartmentRepository:
    return ApartmentRepository(
        session
    )


PhotoApartmentRepositoryDep = Annotated[
    ApartmentRepository,
    Depends(
        get_photo_apartment_repository
    ),
]


def get_apartment_photo_service(
    session: DatabaseSession,
    apartments: PhotoApartmentRepositoryDep,
    photos: ApartmentPhotoRepositoryDep,
    storage: ObjectStorageDep,
) -> ApartmentPhotoService:
    return ApartmentPhotoService(
        session=session,
        apartments=apartments,
        photos=photos,
        storage=storage,
    )


ApartmentPhotoServiceDep = Annotated[
    ApartmentPhotoService,
    Depends(
        get_apartment_photo_service
    ),
]
