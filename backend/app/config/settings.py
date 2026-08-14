from functools import lru_cache
from uuid import UUID

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_LOCAL_DATABASE_URL = "sqlite+aiosqlite:///./khlim_assist_dev.sqlite3"


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "KHLIM Assist"
    log_level: str = "INFO"

    database_url: str = DEFAULT_LOCAL_DATABASE_URL

    openai_api_key: str | None = None

    meta_verify_token: str | None = None
    meta_access_token: str | None = None
    meta_phone_number_id: str | None = None
    meta_app_secret: str | None = None

    active_event_id: UUID | None = None

    api_v1_prefix: str = Field(default="/api/v1", exclude=True)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator(
        "openai_api_key",
        "meta_verify_token",
        "meta_access_token",
        "meta_phone_number_id",
        "meta_app_secret",
        mode="before",
    )
    @classmethod
    def blank_secret_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def default_database_url_when_blank(cls, value: object) -> object:
        if value is None:
            return DEFAULT_LOCAL_DATABASE_URL
        if isinstance(value, str) and not value.strip():
            return DEFAULT_LOCAL_DATABASE_URL
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
