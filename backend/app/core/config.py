from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "CutNote"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    DATABASE_URL: str = "sqlite+aiosqlite:///./cutnote_dev.db"

    JWT_SECRET_KEY: str = Field(default="dev-only-change-me-32-chars-minimum-jwt")
    REVIEW_HMAC_SECRET: str = Field(default="dev-only-change-me-32-chars-minimum-hmac")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    COOKIE_NAME: str = "cutnote_session"
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"

    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]

    STORAGE_LOCAL_ROOT: str = "./storage_data"
    MAX_VIDEO_SIZE_BYTES: int = 500 * 1024 * 1024
    MAX_CHUNK_SIZE_BYTES: int = 10 * 1024 * 1024
    MAX_VOICE_SIZE_BYTES: int = 10 * 1024 * 1024
    MAX_VIDEO_DURATION_SECONDS: int = 1800
    MAX_VOICE_DURATION_SECONDS: int = 120
    MAX_JSON_BODY_BYTES: int = 1 * 1024 * 1024

    @property
    def cookie_secure(self) -> bool:
        return self.ENVIRONMENT != "development"

    @field_validator("JWT_SECRET_KEY", "REVIEW_HMAC_SECRET")
    @classmethod
    def validate_secret_length(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("Cryptographic secrets must be at least 32 characters long.")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()