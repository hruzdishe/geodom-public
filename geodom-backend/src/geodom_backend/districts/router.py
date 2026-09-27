from fastapi import APIRouter, HTTPException, status

from geodom_backend.db.models import District
from geodom_backend.districts.dependencies import DistrictServiceDep
from geodom_backend.districts.exceptions import DistrictNotFoundError
from geodom_backend.districts.schemas import DistrictResponse

router = APIRouter(
    prefix="/districts",
    tags=["Districts"]
)

@router.get(
    "",
    response_model=list[DistrictResponse]
)
async def get_districts(service: DistrictServiceDep) -> list[District]:
    return await service.get_all()

@router.get(
    "/{district_id}",
    response_model=DistrictResponse
)
async def get_district(district_id: int, service: DistrictServiceDep) -> District:
    try:
        return await service.get_by_id(district_id)
    except DistrictNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="District not found"
        ) from e
