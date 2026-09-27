from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status

from geodom_backend.apartments.dependencies import ApartmentServiceDep
from geodom_backend.apartments.enums import ApartmentDealType, RentPeriod
from geodom_backend.apartments.exceptions import (
    ApartmentNotFoundError,
    ApartmentPermissionError,
    InvalidApartmentDataError,
)
from geodom_backend.apartments.presenter_dependencies import (
    ApartmentPresenterDep,
)
from geodom_backend.apartments.queries import ApartmentQuery
from geodom_backend.apartments.schemas import (
    ApartmentCreateRequest,
    ApartmentDetailResponse,
    ApartmentFilters,
    ApartmentListResponse,
    ApartmentResponse,
    ApartmentUpdateRequest,
)
from geodom_backend.auth.dependencies import CurrentUser
from geodom_backend.geo.exceptions import (
    AddressNotFoundError,
    AddressOutsideCityError,
    DistrictNotResolvedError,
    GeocodingUnavailableError,
)

router = APIRouter(
    prefix="/apartments",
    tags=["Apartments"],
)

@router.get(
    "",
    response_model=ApartmentListResponse,
)
async def get_apartments(
    service: ApartmentServiceDep,
    presenter: ApartmentPresenterDep,
    deal_type: ApartmentDealType | None = Query(default=None),
    rent_period: RentPeriod | None = Query(default=None),
    price_min: Decimal | None = Query(default=None, ge=0),
    price_max: Decimal | None = Query(default=None, ge=0),
    rooms: int | None = Query(default=None, ge=0),
    district_id: int | None = Query(default=None, gt=0),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
) -> ApartmentListResponse:
    if (
        price_min is not None
        and price_max is not None
        and price_min > price_max
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="price_min cannot be greater than price_max",
        )

    if (
        rent_period is not None
        and deal_type != ApartmentDealType.RENT
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="rent_period can only be used with deal_type=rent",
        )

    query = ApartmentQuery(
        deal_type=deal_type,
        rent_period=rent_period,
        price_min=price_min,
        price_max=price_max,
        rooms=rooms,
        district_id=district_id,
    )

    page = await service.get_catalog(
        query=query,
        limit=limit,
        offset=offset,
    )

    items = [
        await presenter.response(
            apartment,
            public_only=True,
        )
        for apartment in page.items
    ]

    return ApartmentListResponse(
        items=items,
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )

@router.get(
    "/my",
    response_model=list[ApartmentResponse]
)
async def get_my_apartments(
    user: CurrentUser,
    service: ApartmentServiceDep,
    presenter: ApartmentPresenterDep,
) -> list[ApartmentResponse]:
    apartments = await service.get_my_apartments(user=user)

    return [
        await presenter.response(apartment, public_only=False)
        for apartment in apartments
    ]

@router.get(
    "/my/{apartment_id}",
    response_model=ApartmentDetailResponse
)
async def get_my_apartment(
    apartment_id: int,
    user: CurrentUser,
    service: ApartmentServiceDep,
    presenter: ApartmentPresenterDep,
) -> ApartmentDetailResponse:
    try:
        apartment = await service.get_my_apartment(
            apartment_id=apartment_id,
            user=user,
        )
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

    return await presenter.detail(apartment, public_only=False)

@router.post(
    "",
    response_model=ApartmentDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_apartment(
    data: ApartmentCreateRequest,
    user: CurrentUser,
    service: ApartmentServiceDep,
    presenter: ApartmentPresenterDep,
) -> ApartmentDetailResponse:
    try:
        apartment = await service.create(
            user=user,
            data=data,
        )

    except AddressNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Address not found",
        ) from exc

    except AddressOutsideCityError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Apartment must be located in Krasnoyarsk",
        ) from exc

    except DistrictNotResolvedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="District could not be determined",
        ) from exc

    except GeocodingUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Geocoding service unavailable",
        ) from exc

    return await presenter.detail(apartment, public_only=False)


@router.patch(
    "/{apartment_id}",
    response_model=ApartmentDetailResponse,
)
async def update_apartment(
    apartment_id: int,
    data: ApartmentUpdateRequest,
    user: CurrentUser,
    service: ApartmentServiceDep,
    presenter: ApartmentPresenterDep,
) -> ApartmentDetailResponse:
    try:
        apartment = await service.update(
            apartment_id=apartment_id,
            user=user,
            data=data,
        )

    except ApartmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Apartment not found",
        ) from exc

    except ApartmentPermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot edit this apartment",
        ) from exc

    except InvalidApartmentDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    except AddressNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Address not found",
        ) from exc

    except AddressOutsideCityError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Apartment must be located in Krasnoyarsk",
        ) from exc

    except DistrictNotResolvedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="District could not be determined",
        ) from exc

    except GeocodingUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Geocoding service unavailable",
        ) from exc

    return await presenter.detail(apartment, public_only=True)

@router.post(
    "/{apartment_id}/hide",
    response_model=ApartmentDetailResponse,
)
async def hide_apartment(
    apartment_id: int,
    user: CurrentUser,
    service: ApartmentServiceDep,
    presenter: ApartmentPresenterDep,
) -> ApartmentDetailResponse:
    try:
        apartment = await service.hide(
            apartment_id=apartment_id,
            user=user,
        )

    except ApartmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Apartment not found",
        ) from exc

    except ApartmentPermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot modify this apartment",
        ) from exc

    return await presenter.detail(apartment, public_only=False)


@router.post(
    "/{apartment_id}/publish",
    response_model=ApartmentDetailResponse,
)
async def publish_apartment(
    apartment_id: int,
    user: CurrentUser,
    service: ApartmentServiceDep,
    presenter: ApartmentPresenterDep,
) -> ApartmentDetailResponse:
    try:
        apartment = await service.publish(
            apartment_id=apartment_id,
            user=user,
        )

    except ApartmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Apartment not found",
        ) from exc

    except ApartmentPermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot modify this apartment",
        ) from exc

    return await presenter.detail(apartment, public_only=False)


@router.delete(
    "/{apartment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_apartment(
    apartment_id: int,
    user: CurrentUser,
    service: ApartmentServiceDep,
) -> None:
    try:
        await service.delete(
            apartment_id=apartment_id,
            user=user,
        )

    except ApartmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Apartment not found",
        ) from exc

    except ApartmentPermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot delete this apartment",
        ) from exc


@router.get(
    "/{apartment_id}",
    response_model=ApartmentDetailResponse,
)
async def get_apartment(
    apartment_id: int,
    service: ApartmentServiceDep,
    presenter: ApartmentPresenterDep,
) -> ApartmentDetailResponse:
    try:
        apartment = await service.get_public_by_id(
            apartment_id
        )

    except ApartmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Apartment not found",
        ) from exc

    return await presenter.detail(apartment, public_only=True)
