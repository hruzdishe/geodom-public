from datetime import datetime

from pydantic import BaseModel, ConfigDict

from geodom_backend.db.models import UserRole

class UserResponse(BaseModel):
    id: int
    login: str
    role: UserRole
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
