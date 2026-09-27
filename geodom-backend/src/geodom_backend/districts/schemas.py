from pydantic import BaseModel, ConfigDict


class DistrictResponse(BaseModel):
    id: int
    name: str
    description: str | None
    center_latitude: float | None
    center_longitude: float | None

    model_config = ConfigDict(from_attributes=True)
