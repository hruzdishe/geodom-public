from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from geodom_backend.apartments.exceptions import ApartmentNotFoundError, ApartmentPermissionError
from geodom_backend.apartments.photo_dependencies import ApartmentPhotoServiceDep
from geodom_backend.apartments.photo_exceptions import ApartmentPhotoLimitError, ApartmentPhotoNotFoundError, InvalidApartmentPhotoError, InvalidPhotoOrderError
from geodom_backend.apartments.photo_schemas import ApartmentPhotoOrderRequest
from geodom_backend.apartments.schemas import ApartmentPhotoResponse
from geodom_backend.auth.dependencies import CurrentUser
from geodom_backend.storage.exceptions import ObjectStorageUnavailableError

router = APIRouter(
    prefix="/apartments",
    tags=["Apartment Photos"]
)

@router.get(
    "/my/{apartment_id}/photos",
    response_model=list[ApartmentPhotoResponse]
)
async def get_my_apartment_photos(
    apartment_id: int,
    user: CurrentUser,
    service: ApartmentPhotoServiceDep
) -> list[ApartmentPhotoResponse]:
    try:
        return await service.get_my_photos(apartment_id=apartment_id, user=user)
    except ApartmentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Apartment not found"
        ) from e
    except ApartmentPermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot access this apartment"
        ) from e
    except ObjectStorageUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object storage unavailable"
        ) from e

@router.post(
    "/{apartment_id}/photos",
    response_model=ApartmentPhotoResponse,
    status_code=status.HTTP_201_CREATED
)
async def upload_apartment_photo(
    apartment_id: int,
    user: CurrentUser,
    service: ApartmentPhotoServiceDep,
    file: Annotated[
        UploadFile,
        File()
    ],
    is_cover: bool = Query(default=False)
) -> ApartmentPhotoResponse:
    try:
        return await service.upload(
            apartment_id=apartment_id,
            user=user,
            file=file,
            is_cover=is_cover
        )
    except ApartmentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Apartment not found"
        ) from e
    except ApartmentPermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot modify this apartment"
        ) from e
    except InvalidApartmentPhotoError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e)
        ) from e
    except ApartmentPhotoLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        ) from e
    except ObjectStorageUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object storage unavailable"
        ) from e

@router.delete(
    "/{apartment_id}/photos/{photo_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_apartment_photo(
    apartment_id: int,
    photo_id: int,
    user: CurrentUser,
    service: ApartmentPhotoServiceDep
):
    try:
        await service.delete(
            apartment_id=apartment_id,
            photo_id=photo_id,
            user=user
        )
    except ApartmentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Apartment not found"
        ) from e
    except ApartmentPhotoNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found"
        ) from e
    except ApartmentPermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot modify this apartment"
        ) from e

@router.post(
    "/{apartment_id}/photos/{photo_id}/cover",
    response_model=ApartmentPhotoResponse
)
async def set_apartment_cover_photo(
    apartment_id: int,
    photo_id: int,
    user: CurrentUser,
    service: ApartmentPhotoServiceDep
) -> ApartmentPhotoResponse:
    try:
        return await service.set_cover(
            apartment_id=apartment_id,
            photo_id=photo_id,
            user=user
        )
    except ApartmentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Apartment not found"
        ) from e
    except ApartmentPhotoNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found"
        ) from e
    except ApartmentPermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot modify this apartment"
        ) from e
    except ObjectStorageUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object storage unavailable"
        ) from e

@router.put(
    "/{apartment_id}/photos/order",
    response_model=list[
        ApartmentPhotoResponse
    ]
)
async def reordeR_apartment_photos(
    apartment_id: int,
    data: ApartmentPhotoOrderRequest,
    user: CurrentUser,
    service: ApartmentPhotoServiceDep
) -> list[ApartmentPhotoResponse]:
    try:
        return await service.reorder(
            apartment_id=apartment_id,
            photo_ids=data.photo_ids,
            user=user
        )
    except ApartmentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Apartment not found"
        ) from e
    except ApartmentPermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot modify this apartment"
        ) from e
    except InvalidPhotoOrderError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e)
        ) from e
    except ObjectStorageUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object storage unavailable"
        ) from e
