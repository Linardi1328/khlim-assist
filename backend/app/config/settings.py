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
    openai_model: str | None = None
    openai_request_timeout_seconds: float = 30.0

    ai_processing_enabled: bool = False
    ai_shadow_mode: bool = True
    ai_auto_reply_enabled: bool = False
    ai_context_message_limit: int = 10

    meta_graph_api_base_url: str = "https://graph.facebook.com"
    meta_graph_api_version: str | None = None
    meta_waba_id: str | None = None
    meta_verify_token: str | None = None
    meta_access_token: str | None = None
    meta_phone_number_id: str | None = None
    meta_app_secret: str | None = None

    whatsapp_sandbox_mode: bool = True
    whatsapp_outbound_enabled: bool = False
    whatsapp_allowed_recipients: tuple[str, ...] = ()
    whatsapp_request_timeout_seconds: float = 10.0

    active_event_id: UUID | None = None

    api_v1_prefix: str = Field(default="/api/v1", exclude=True)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator(
        "openai_api_key",
        "openai_model",
        "meta_graph_api_version",
        "meta_waba_id",
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

    @field_validator("whatsapp_allowed_recipients", mode="before")
    @classmethod
    def parse_allowed_recipients(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, str):
            if not value.strip():
                return ()
            return tuple(item.strip() for item in value.split(",") if item.strip())
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
