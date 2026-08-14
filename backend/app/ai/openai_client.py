import json
from copy import deepcopy
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
from app.ai.prompts import INTERPRETATION_SYSTEM_PROMPT, RESPONSE_STYLE_SYSTEM_PROMPT
from app.config.settings import Settings, get_settings
from app.schemas.enums import IntentType, KnowledgeTopic
from app.schemas.interpretation import InterpretationRequest, InterpretedMessage


class _ResponsesResource(Protocol):
    async def create(self, **kwargs: Any) -> object:
        """Create a Responses API response."""


class _OpenAIClient(Protocol):
    responses: _ResponsesResource


class OpenAIProvider:
    """Lazy OpenAI Responses API wrapper.

    The SDK client is not constructed until an AI method is called, so application startup and
    tests do not require network access or credentials.
    """

    provider_name = "openai"

    def __init__(
        self,
        settings: Settings | None = None,
        model: str | None = None,
        client: _OpenAIClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.model = model or self.settings.openai_model
        self._client = client
        self.interpretation_metadata: AIProviderCallMetadata | None = None
        self.response_metadata: AIProviderCallMetadata | None = None

    @property
    def client(self) -> _OpenAIClient:
        if not self.settings.openai_api_key:
            raise AIProviderUnavailable("OPENAI_API_KEY is required for OpenAI AI calls.")
        if not self.model:
            raise AIProviderUnavailable("OPENAI_MODEL is required for OpenAI AI calls.")
        if self._client is None:
            self._client = cast(
                _OpenAIClient,
                AsyncOpenAI(api_key=self.settings.openai_api_key),
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
            raise _map_openai_error(exc) from exc

        self.interpretation_metadata = _metadata_from_response(response)
        content = _response_output_text(response)
        try:
            return InterpretedMessage.model_validate_json(content)
        except (ValidationError, ValueError) as exc:
            raise AIProviderResponseError("OpenAI returned malformed interpretation JSON") from exc

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
            raise _map_openai_error(exc) from exc

        self.response_metadata = _metadata_from_response(response)
        content = _response_output_text(response).strip()
        if not content:
            raise AIProviderResponseError("OpenAI returned an empty response draft")
        return GeneratedResponse(text=content, should_send=False)

    async def _create_response(
        self,
        *,
        instructions: str,
        input_text: str,
        text_format: dict[str, object] | None = None,
    ) -> object:
        if not self.model:
            raise AIProviderUnavailable("OPENAI_MODEL is required for OpenAI AI calls.")
        kwargs: dict[str, object] = {
            "model": self.model,
            "instructions": instructions,
            "input": input_text,
            "store": False,
            "background": False,
            "tools": [],
            "timeout": self.settings.openai_request_timeout_seconds,
        }
        if text_format is not None:
            kwargs["text"] = {"format": text_format}
        return await self.client.responses.create(**kwargs)


def _response_output_text(response: object) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text:
        return output_text

    output = getattr(response, "output", None)
    if isinstance(output, list):
        chunks: list[str] = []
        for output_item in output:
            content = getattr(output_item, "content", None)
            if not isinstance(content, list):
                continue
            for content_item in content:
                text = getattr(content_item, "text", None)
                if isinstance(text, str):
                    chunks.append(text)
        if chunks:
            return "".join(chunks)

    raise AIProviderResponseError("OpenAI response did not include output text")


def _strict_interpretation_schema() -> dict[str, Any]:
    schema = deepcopy(InterpretedMessage.model_json_schema())
    message_intent = schema.get("$defs", {}).get("MessageIntent")
    if isinstance(message_intent, dict):
        properties = message_intent.get("properties")
        if isinstance(properties, dict):
            properties["entities"] = _strict_entities_schema()
    _normalize_strict_schema(schema)
    return schema


def _strict_entities_schema() -> dict[str, Any]:
    nullable_string = {"anyOf": [{"type": "string"}, {"type": "null"}]}
    nullable_integer = {"anyOf": [{"type": "integer"}, {"type": "null"}]}
    nullable_boolean = {"anyOf": [{"type": "boolean"}, {"type": "null"}]}
    properties: dict[str, Any] = {
        "birth_year": nullable_integer,
        "foreign_player": nullable_boolean,
        "foreign_player_count": nullable_boolean,
        "national_player": nullable_boolean,
        "single_player": nullable_boolean,
        "whole_team": nullable_boolean,
        "mixed_gender": nullable_boolean,
        "minimum_players": nullable_integer,
        "maximum_players": nullable_integer,
        "requested_players": nullable_integer,
        "registration_fee": nullable_boolean,
        "category_fee": nullable_boolean,
        "early_bird_fee": nullable_boolean,
        "early_bird_deadline": nullable_boolean,
        "requested_category": nullable_string,
    }
    return {
        "type": "object",
        "title": "Entities",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _normalize_strict_schema(node: object) -> None:
    if isinstance(node, dict):
        node.pop("default", None)
        if node.get("type") == "object":
            properties = node.get("properties")
            if isinstance(properties, dict):
                node["required"] = list(properties)
            node["additionalProperties"] = False
        for value in node.values():
            _normalize_strict_schema(value)
    elif isinstance(node, list):
        for item in node:
            _normalize_strict_schema(item)


def _metadata_from_response(response: object) -> AIProviderCallMetadata:
    usage = getattr(response, "usage", None)
    request_id = getattr(response, "id", None)
    return AIProviderCallMetadata(
        provider_request_id=request_id if isinstance(request_id, str) else None,
        input_tokens=_int_attr(usage, "input_tokens"),
        output_tokens=_int_attr(usage, "output_tokens"),
        total_tokens=_int_attr(usage, "total_tokens"),
    )


def _int_attr(value: object, attribute: str) -> int | None:
    if value is None:
        return None
    raw = value.get(attribute) if isinstance(value, dict) else getattr(value, attribute, None)
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    return None


def _map_openai_error(exc: Exception) -> Exception:
    if isinstance(exc, AuthenticationError):
        return AIProviderAuthenticationError("OpenAI rejected authentication")
    if isinstance(exc, RateLimitError):
        return AIProviderRateLimitError("OpenAI rate limit reached")
    if isinstance(exc, APITimeoutError):
        return AIProviderTimeoutError("OpenAI request timed out")
    if isinstance(exc, APIStatusError):
        status_code = getattr(exc, "status_code", None)
        return AIProviderRequestError(f"OpenAI request failed with status {status_code}")
    if isinstance(exc, APIConnectionError):
        return AIProviderRequestError("OpenAI request failed at the transport layer")
    return exc
