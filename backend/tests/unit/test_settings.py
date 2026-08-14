from uuid import uuid4

from app.config.settings import DEFAULT_LOCAL_DATABASE_URL, Settings


def test_settings_blank_values_are_safe() -> None:
    settings = Settings(database_url="", openai_api_key="", meta_verify_token="")

    assert settings.database_url == DEFAULT_LOCAL_DATABASE_URL
    assert settings.openai_api_key is None
    assert settings.meta_verify_token is None


def test_settings_accept_active_event_uuid() -> None:
    event_id = uuid4()
    settings = Settings(active_event_id=str(event_id))

    assert settings.active_event_id == event_id
