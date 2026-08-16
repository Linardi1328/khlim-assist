import pytest
from app.ai.base import AIProviderUnavailable
from app.ai.fake import FakeAIProvider
from app.ai.groq_client import GroqProvider
from app.ai.openai_client import OpenAIProvider
from app.ai.providers import create_ai_provider
from app.config.settings import Settings
from app.schemas.enums import AIProviderName


def test_ai_provider_factory_uses_configured_groq_provider() -> None:
    provider = create_ai_provider(Settings(ai_provider=AIProviderName.GROQ))

    assert isinstance(provider, GroqProvider)
    assert provider.provider_name == "groq"


def test_ai_provider_factory_uses_configured_openai_provider() -> None:
    provider = create_ai_provider(Settings(ai_provider=AIProviderName.OPENAI))

    assert isinstance(provider, OpenAIProvider)
    assert provider.provider_name == "openai"


def test_ai_provider_factory_allows_explicit_fake_test_provider() -> None:
    provider = create_ai_provider(Settings(ai_provider=AIProviderName.GROQ), "fake")

    assert isinstance(provider, FakeAIProvider)
    assert provider.provider_name == "fake"


def test_ai_provider_factory_rejects_invalid_provider() -> None:
    with pytest.raises(AIProviderUnavailable) as exc_info:
        create_ai_provider(Settings(), "invalid")

    assert "Unsupported AI provider" in str(exc_info.value)
    assert "fake, openai, groq" in str(exc_info.value)


def test_ai_provider_factory_rejects_empty_explicit_provider() -> None:
    with pytest.raises(AIProviderUnavailable):
        create_ai_provider(Settings(), "")


def test_ai_provider_factory_does_not_allow_fake_in_production() -> None:
    with pytest.raises(AIProviderUnavailable):
        create_ai_provider(Settings(app_env="production"), "fake")
