from uuid import uuid4

from app.config.settings import DEFAULT_LOCAL_DATABASE_URL, Settings
from app.schemas.enums import AIProviderName


def test_settings_blank_values_are_safe() -> None:
    settings = Settings(
        database_url="",
        openai_api_key="",
        groq_api_key="",
        groq_model="",
        meta_verify_token="",
    )

    assert settings.database_url == DEFAULT_LOCAL_DATABASE_URL
    assert settings.openai_api_key is None
    assert settings.groq_api_key is None
    assert settings.groq_model is None
    assert settings.meta_verify_token is None


def test_settings_accept_active_event_uuid() -> None:
    event_id = uuid4()
    settings = Settings(active_event_id=str(event_id))

    assert settings.active_event_id == event_id


def test_phase_1_whatsapp_settings_defaults_are_safe() -> None:
    settings = Settings()

    assert settings.meta_graph_api_base_url == "https://graph.facebook.com"
    assert settings.meta_graph_api_version is None
    assert settings.whatsapp_sandbox_mode is True
    assert settings.whatsapp_outbound_enabled is False
    assert settings.whatsapp_allowed_recipients == ()


def test_phase_1_allowed_recipients_parse_comma_separated_values() -> None:
    settings = Settings(whatsapp_allowed_recipients="15550000001, 15550000002")

    assert settings.whatsapp_allowed_recipients == ("15550000001", "15550000002")


def test_phase_2_ai_settings_defaults_are_safe() -> None:
    settings = Settings()

    assert settings.ai_provider == AIProviderName.GROQ
    assert settings.openai_model is None
    assert settings.openai_request_timeout_seconds == 30
    assert settings.groq_model == "openai/gpt-oss-120b"
    assert settings.groq_api_base_url == "https://api.groq.com/openai/v1"
    assert settings.groq_request_timeout_seconds == 30
    assert settings.ai_processing_enabled is False
    assert settings.ai_shadow_mode is True
    assert settings.ai_auto_reply_enabled is False
    assert settings.ai_context_message_limit == 10
