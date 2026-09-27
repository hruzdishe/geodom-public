from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from geodom_backend.apartments.enums import ApartmentDealType
from geodom_backend.apartments.schemas import ApartmentResponse

PriorityWeight = Annotated[
    int,
    Field(
        strict=True,
        ge=0,
        le=5,
    )
]

class WorkLocationRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)

    max_minutes: float | None = Field(default=None, gt=0, le=1440)

class RecommendationRequest(BaseModel):
    price_min: int | None = Field(
        default=None,
        ge=0
    )

    price_max: int | None = Field(
        default=None,
        ge=0
    )

    rooms: list[
        Annotated[
            int,
            Field(
                strict=True,
                ge=0,
                le=20
            )
        ]
    ] = Field(default_factory=list)

    districts: list[str] = Field(
        default_factory=list
    )

    offer_type: ApartmentDealType = ApartmentDealType.SALE

    children_age_groups: list[
        Literal[
            "preschool", "school"
        ]
    ] = Field(
        default_factory=list
    )

    priorities: dict[str, PriorityWeight] = Field(default_factory=dict)

    work: WorkLocationRequest | None = None

    limit: int = Field(default=10, ge=1, le=100)

    @model_validator(mode="after")
    def validate_request(self) -> "RecommendationRequest":
        if self.price_min is not None and self.price_max is not None and self.price_min > self.price_max:
            raise ValueError("price_min cannot be greater then price_max")

        allowed_priorities = {
            "schools",
            "kindergartens",
            "parks",
            "transport",
            "sport",
            "shopping_centers",
            "healthcare",
            "pharmacies",
            "ecology",
            "safety",
            "cafes",
            "work",
        }

        unknown = set(self.priorities) - allowed_priorities
        if unknown:
            raise ValueError(f"Unknown priorities: {sorted(unknown)}")

        return self

    def scoring_preferences(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"limit"})

class RecommendationComponentResponse(BaseModel):
    priority: str
    label: str

    weight: int

    distance_m: float | None
    nearest_poi_id: str | None
    half_score_distance_m: float
    score: float | None
    contribution_points: float
    status: str
    explanation: str

class RecommendationItemResponse(BaseModel):
    rank: int

    apartment: ApartmentResponse

    score: float | None
    score_upper_bound: float | None
    score_coverage: float

    scoring_status: str

    components: list[
        RecommendationComponentResponse
    ]

    commute: dict[str, Any] | None

class RecommendationResponse(BaseModel):
    request_id: UUID

    model_version: str
    scoring_version: str

    fallback_used: bool

    status: str

    eligible_count: int
    returned_count: int

    filter_rejection_counts: dict[str, int]

    unsupported_priorities: list[dict[str, Any]]

    limitations: list[str]

    items: list[RecommendationItemResponse]
