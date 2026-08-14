import json
from typing import Any, Protocol, cast

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
)
from pydantic import ValidationError

from app.ai.base import (
    AIProviderAuthenticationError,
    AIProviderCallMetadata,
    AIProviderRateLimitError,
    AIProviderRequestError,
    AIProviderResponseError,
    AIProviderTimeoutError,
    AIProviderUnavailable,
    GeneratedResponse,
    ResponseGenerationRequest,
)
from app.ai.openai_client import (
    _metadata_from_response,
    _response_output_text,
    _strict_interpretation_schema,
)
from app.ai.prompts import INTERPRETATION_SYSTEM_PROMPT, RESPONSE_STYLE_SYSTEM_PROMPT
from app.config.settings import Settings, get_settings
from app.schemas.enums import IntentType, KnowledgeTopic
from app.schemas.interpretation import InterpretationRequest, InterpretedMessage


class _ResponsesResource(Protocol):
    async def create(self, **kwargs: Any) -> object:
        """Create a Responses API response."""


class _GroqClient(Protocol):
    responses: _ResponsesResource


class GroqProvider:
    """Lazy Groq Responses API wrapper using the OpenAI-compatible SDK client."""

    provider_name = "groq"

    def __init__(
        self,
        settings: Settings | None = None,
        model: str | None = None,
        client: _GroqClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.model = model or self.settings.groq_model
        self._client = client
        self.interpretation_metadata: AIProviderCallMetadata | None = None
        self.response_metadata: AIProviderCallMetadata | None = None

    @property
    def client(self) -> _GroqClient:
        if not self.settings.groq_api_key:
            raise AIProviderUnavailable("GROQ_API_KEY is required for Groq AI calls.")
        if not self.model:
            raise AIProviderUnavailable("GROQ_MODEL is required for Groq AI calls.")
        if self._client is None:
            self._client = cast(
                _GroqClient,
                AsyncOpenAI(
                    api_key=self.settings.groq_api_key,
                    base_url=self.settings.groq_api_base_url,
                ),
            )
        return self._client

    async def interpret_message(self, request: InterpretationRequest) -> InterpretedMessage:
        payload = {
            "participant_message": request.message_text,
            "channel": request.channel,
            "event_id": request.event_id,
            "conversation_id": request.conversation_id,
            "recent_context": [item.model_dump() for item in request.recent_messages],
            "allowed_intent_values": [item.value for item in IntentType],
            "allowed_knowledge_topic_values": [item.value for item in KnowledgeTopic],
        }
        try:
            response = await self._create_response(
                instructions=INTERPRETATION_SYSTEM_PROMPT,
                input_text=json.dumps(payload, ensure_ascii=False),
                text_format={
                    "type": "json_schema",
                    "name": "khlim_interpreted_message",
                    "schema": _strict_interpretation_schema(),
                    "strict": True,
                },
            )
        except AIProviderResponseError:
            raise
        except (
            APIConnectionError,
            APIStatusError,
            APITimeoutError,
            AuthenticationError,
            RateLimitError,
        ) as exc:
            raise _map_groq_error(exc) from exc

        self.interpretation_metadata = _metadata_from_response(response)
        content = _groq_response_output_text(response)
        try:
            return InterpretedMessage.model_validate_json(content)
        except (ValidationError, ValueError) as exc:
            raise AIProviderResponseError("Groq returned malformed interpretation JSON") from exc

    async def generate_response(self, request: ResponseGenerationRequest) -> GeneratedResponse:
        payload = {
            "participant_message": request.participant_text,
            "response_language": request.response_language,
            "decision": request.decision_result.model_dump(mode="json"),
            "approved_knowledge": [
                result.model_dump(mode="json") for result in request.knowledge_results
            ],
            "conversation_context": request.conversation_context,
        }
        try:
            response = await self._create_response(
                instructions=RESPONSE_STYLE_SYSTEM_PROMPT,
                input_text=json.dumps(payload, ensure_ascii=False),
            )
        except AIProviderResponseError:
            raise
        except (
            APIConnectionError,
            APIStatusError,
            APITimeoutError,
            AuthenticationError,
            RateLimitError,
        ) as exc:
            raise _map_groq_error(exc) from exc

        self.response_metadata = _metadata_from_response(response)
        content = _groq_response_output_text(response).strip()
        if not content:
            raise AIProviderResponseError("Groq returned an empty response draft")
        return GeneratedResponse(text=content, should_send=False)

    async def _create_response(
        self,
        *,
        instructions: str,
        input_text: str,
        text_format: dict[str, object] | None = None,
    ) -> object:
        if not self.model:
            raise AIProviderUnavailable("GROQ_MODEL is required for Groq AI calls.")
        kwargs: dict[str, object] = {
            "model": self.model,
            "instructions": instructions,
            "input": input_text,
            "background": False,
            "tools": [],
            "timeout": self.settings.groq_request_timeout_seconds,
        }
        if text_format is not None:
            kwargs["text"] = {"format": text_format}
        return await self.client.responses.create(**kwargs)


def _groq_response_output_text(response: object) -> str:
    try:
        return _response_output_text(response)
    except AIProviderResponseError as exc:
        raise AIProviderResponseError("Groq response did not include output text") from exc


def _map_groq_error(exc: Exception) -> Exception:
    if isinstance(exc, AuthenticationError):
        return AIProviderAuthenticationError("Groq rejected authentication")
    if isinstance(exc, RateLimitError):
        return AIProviderRateLimitError("Groq rate limit reached")
    if isinstance(exc, APITimeoutError):
        return AIProviderTimeoutError("Groq request timed out")
    if isinstance(exc, APIStatusError):
        status_code = getattr(exc, "status_code", None)
        return AIProviderRequestError(f"Groq request failed with status {status_code}")
    if isinstance(exc, APIConnectionError):
        return AIProviderRequestError("Groq request failed at the transport layer")
    return exc
