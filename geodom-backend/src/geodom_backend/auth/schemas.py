from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from geodom_backend.users.schemas import UserResponse

Login = Annotated[
    str,
    Field(
        min_length=3,
        max_length=64
    )
]

Password = Annotated[
    str,
    Field(
        min_length=6,
        max_length=128
    )
]

class RegisterRequest(BaseModel):
    login: Login
    password: Password

    @field_validator("login", mode="before")
    @classmethod
    def normalize_login(cls, value: object) -> object:
        if isinstance(value, str): return value.strip().lower()
        return value

class LoginRequest(BaseModel):
    login: Login
    password: Password

    @field_validator("login", mode="before")
    @classmethod
    def normalize_login(cls, value: object) -> object:
        if isinstance(value, str): return value.strip().lower()
        return value

class AuthResponse(BaseModel):
    user: UserResponse
