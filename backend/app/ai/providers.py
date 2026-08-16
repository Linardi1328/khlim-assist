from app.ai.base import AIProvider, AIProviderUnavailable
from app.ai.fake import FakeAIProvider
from app.ai.groq_client import GroqProvider
from app.ai.openai_client import OpenAIProvider
from app.config.settings import Settings, get_settings
from app.schemas.enums import AIProviderName, AppEnvironment


def provider_choices() -> list[str]:
    return [provider.value for provider in AIProviderName]


def normalize_ai_provider_name(value: AIProviderName | str) -> AIProviderName:
    if isinstance(value, AIProviderName):
        return value
    try:
        return AIProviderName(value.strip().lower())
    except ValueError as exc:
        supported = ", ".join(provider_choices())
        raise AIProviderUnavailable(
            f"Unsupported AI provider '{value}'. Supported providers: {supported}."
        ) from exc


def create_ai_provider(
    settings: Settings | None = None,
    provider_name: AIProviderName | str | None = None,
) -> AIProvider:
    resolved_settings = settings or get_settings()
    raw_provider = resolved_settings.ai_provider if provider_name is None else provider_name
    selected = normalize_ai_provider_name(raw_provider)

    if selected == AIProviderName.FAKE:
        if resolved_settings.app_env == AppEnvironment.PRODUCTION.value:
            raise AIProviderUnavailable("FakeAIProvider cannot be selected in production.")
        return FakeAIProvider()
    if selected == AIProviderName.OPENAI:
        return OpenAIProvider(resolved_settings)
    if selected == AIProviderName.GROQ:
        return GroqProvider(resolved_settings)

    supported = ", ".join(provider_choices())
    raise AIProviderUnavailable(f"Unsupported AI provider '{selected}'. Supported: {supported}.")
