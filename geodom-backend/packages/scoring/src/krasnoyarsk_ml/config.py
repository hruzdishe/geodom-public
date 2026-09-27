from pathlib import Path

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ML_", env_file=".env", extra="ignore")

    data_dir: Path = Path("data")
    overpass_url: HttpUrl = "https://overpass.private.coffee/api/interpreter"
    timeout_seconds: float = Field(default=240, gt=0)
    query_timeout_seconds: int = Field(default=180, ge=1, le=600)
    attempts: int = Field(default=3, ge=1, le=5)
    backoff_seconds: float = Field(default=5, ge=0, le=60)
    max_address_m: float = Field(default=75, gt=0, le=500)
    max_street_m: float = Field(default=150, gt=0, le=500)
