from fastapi import APIRouter

from geodom_backend.apartments.photo_router import router as apartment_photos_router
from geodom_backend.apartments.router import router as apartments_router
from geodom_backend.auth.router import router as auth_router
from geodom_backend.districts.router import router as districts_router
from geodom_backend.recommendations.router import router as recommendations_router

from .infrastructure import router as infrastructure_router

router = APIRouter()
router.include_router(infrastructure_router)

@router.get(
    "/health",
    tags=["Health"],
    summary="Проверить состояние API"
)
async def health_check() -> dict[str, str]:
    return {
        "status": "ok"
    }

router.include_router(auth_router)
router.include_router(districts_router)
router.include_router(apartments_router)
router.include_router(recommendations_router)
router.include_router(apartment_photos_router)
