from pydantic import BaseModel, Field, field_validator

class ApartmentPhotoOrderRequest(BaseModel):
    photo_ids: list[int] = Field(
        min_length=1,
        max_length=10
    )

    @field_validator("photo_ids")
    @classmethod
    def validate_unique_ids(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("photo_ids must be unique")

        if any(photo_id <= 0 for photo_id in value):
            raise ValueError("photo_ids must be positive")

        return value
