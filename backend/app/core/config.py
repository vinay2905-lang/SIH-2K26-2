"""Application configuration loaded from environment variables (see .env.example)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Fixed development-only keys so a fresh checkout runs without setup.
# They are public (committed) and therefore offer NO protection; production refuses them.
DEV_IDENTIFIER_HMAC_KEY = "dev-only-hmac-key-not-secret-change-me-0123456789"
DEV_IDENTIFIER_ENCRYPTION_KEY = "ZGV2LW9ubHktZmVybmV0LWtleS0zMi1ieXRlcyEhISE="


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://apaar:apaar_dev_password@localhost:5432/apaar"

    # Keyed HMAC for identifier matching and Fernet key for identifier encryption at rest.
    identifier_hmac_key: str = DEV_IDENTIFIER_HMAC_KEY
    identifier_encryption_key: str = DEV_IDENTIFIER_ENCRYPTION_KEY

    session_cookie_name: str = "apaar_session"
    session_ttl_minutes: int = Field(default=480, ge=5)
    cookie_secure: bool = False
    cors_origins: list[str] = Field(default_factory=list)

    upload_max_bytes: int = Field(default=5 * 1024 * 1024, ge=1024)
    upload_max_rows: int = Field(default=5000, ge=1)

    login_max_attempts: int = Field(default=5, ge=1)
    login_window_seconds: int = Field(default=900, ge=10)

    frontend_dist_dir: str = "../frontend/dist"

    @model_validator(mode="after")
    def _refuse_dev_keys_in_production(self) -> "Settings":
        if self.app_env == "production":
            if self.identifier_hmac_key == DEV_IDENTIFIER_HMAC_KEY:
                raise ValueError("IDENTIFIER_HMAC_KEY must be set in production")
            if self.identifier_encryption_key == DEV_IDENTIFIER_ENCRYPTION_KEY:
                raise ValueError("IDENTIFIER_ENCRYPTION_KEY must be set in production")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in production")
        return self

    @property
    def using_dev_keys(self) -> bool:
        return (
            self.identifier_hmac_key == DEV_IDENTIFIER_HMAC_KEY
            or self.identifier_encryption_key == DEV_IDENTIFIER_ENCRYPTION_KEY
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
