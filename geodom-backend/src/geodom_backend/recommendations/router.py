from fastapi import APIRouter

from geodom_backend.auth.dependencies import OptionalCurrentUser

from .dependencies import RecommendationServiceDep
from .schemas import RecommendationRequest, RecommendationResponse

router = APIRouter(
    prefix="/recommendations",
    tags=["Recommendations"]
)


@router.post(
    "",
    response_model=RecommendationResponse
)
async def get_recommendations(
    data: RecommendationRequest,
    user: OptionalCurrentUser,
    service: RecommendationServiceDep
) -> RecommendationResponse:
    return await service.recommend(
        data=data,
        user=user
    )
