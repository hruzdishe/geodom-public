from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "GeoDom API"
    app_version: str = "0.1.0"
    debug: bool = True

    api_prefix: str = "/api/v1"

    database_url: str
    database_echo: bool = False

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173"
        ]
    )

    geocoding_base_url: str = "https://nominatim.openstreetmap.org"
    geocoding_user_agent: str = "GeoDom/0.1"
    geocoding_city: str = "Красноярск"
    geocoding_timeout_seconds: float = 10.0

    auth_cookie_name: str = "geodom_session"
    auth_session_ttl_hours: int = 24 * 7
    auth_cookie_secure: bool = False
    auth_cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    storage_endpoint: str = "localhost:9000"
    storage_access_key: str = "minioadmin"
    storage_secret_key: str = "minioadmin"
    storage_secure: bool = False

    storage_user_bucket: str = "geodom-user-media"

    storage_presigned_ttl_seconds: int = 3600

    storage_max_photo_size_bytes: int = 10 * 1024 * 1024
    storage_max_photos_per_apartment: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]

settings = get_settings()
