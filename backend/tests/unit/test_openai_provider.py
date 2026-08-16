from types import SimpleNamespace

import httpx
import pytest
from app.ai.base import (
    AIProviderAuthenticationError,
    AIProviderRateLimitError,
    AIProviderRequestError,
    AIProviderResponseError,
    AIProviderTimeoutError,
    AIProviderUnavailable,
    ResponseGenerationRequest,
)
from app.ai.openai_client import OpenAIProvider
from app.config.settings import Settings
from app.schemas.decision import DecisionResult
from app.schemas.enums import DecisionLevel, IntentType
from app.schemas.interpretation import InterpretationRequest, InterpretedMessage, MessageIntent
from app.schemas.retrieval import KnowledgeResult
from openai import APIStatusError, APITimeoutError, AuthenticationError, RateLimitError


def response_with_text(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        output_text=text,
        id="resp_synthetic",
        usage=SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15),
    )


def provider_with_response(response: object) -> tuple[OpenAIProvider, "FakeResponsesResource"]:
    responses = FakeResponsesResource(response=response)
    provider = OpenAIProvider(
        settings=Settings(openai_api_key="test-api-key", openai_model="test-model"),
        client=FakeClient(responses),
    )
    return provider, responses


@pytest.mark.asyncio
async def test_openai_provider_successful_structured_interpretation() -> None:
    interpreted = InterpretedMessage(
        primary_language="en",
        language_mode="single",
        intents=[MessageIntent(type=IntentType.FEE, category="U16")],
    )
    provider, responses = provider_with_response(response_with_text(interpreted.model_dump_json()))

    result = await provider.interpret_message(
        InterpretationRequest(message_text="How much U16?", channel="WHATSAPP")
    )

    assert result.intents[0].type == IntentType.FEE
    assert responses.calls[0]["store"] is False
    assert responses.calls[0]["background"] is False
    assert responses.calls[0]["tools"] == []
    assert responses.calls[0]["model"] == "test-model"
    assert "temperature" not in responses.calls[0]
    text_config = responses.calls[0]["text"]
    assert isinstance(text_config, dict)
    format_config = text_config["format"]
    assert isinstance(format_config, dict)
    assert format_config["type"] == "json_schema"
    assert format_config["strict"] is True
    schema = format_config["schema"]
    assert isinstance(schema, dict)
    assert schema["additionalProperties"] is False
    intent_schema = schema["$defs"]["MessageIntent"]
    assert intent_schema["additionalProperties"] is False
    assert "knowledge_topic" in intent_schema["properties"]
    assert intent_schema["properties"]["entities"]["additionalProperties"] is False
    assert provider.interpretation_metadata is not None
    assert provider.interpretation_metadata.total_tokens == 15


@pytest.mark.asyncio
async def test_openai_provider_successful_response_generation() -> None:
    provider, responses = provider_with_response(response_with_text("Hi! Approved draft 😊"))

    generated = await provider.generate_response(
        ResponseGenerationRequest(
            interpreted_message=InterpretedMessage(
                primary_language="en",
                language_mode="single",
                intents=[MessageIntent(type=IntentType.FEE, category="U16")],
            ),
            decision_result=DecisionResult(
                level=DecisionLevel.GREEN,
                auto_reply_allowed=True,
                requires_human=False,
            ),
            knowledge_results=[
                KnowledgeResult(
                    intent_type=IntentType.FEE,
                    found=True,
                    source_type="event_rule",
                    source_identifier="rule-1",
                    value={"amount_myr": 180},
                    confirmed=True,
                )
            ],
            response_language="en",
            participant_text="How much U16?",
        )
    )

    assert generated.text == "Hi! Approved draft 😊"
    assert generated.should_send is False
    assert responses.calls[0]["store"] is False
    assert responses.calls[0]["background"] is False
    assert responses.calls[0]["tools"] == []
    assert "temperature" not in responses.calls[0]


@pytest.mark.asyncio
async def test_openai_provider_rejects_malformed_interpretation() -> None:
    provider, _responses = provider_with_response(response_with_text('{"primary_language":"en"}'))

    with pytest.raises(AIProviderResponseError):
        await provider.interpret_message(
            InterpretationRequest(message_text="How much U16?", channel="WHATSAPP")
        )


@pytest.mark.asyncio
async def test_openai_provider_maps_timeout() -> None:
    request = httpx.Request("POST", "https://api.openai.test/responses")
    provider, _responses = provider_with_response(APITimeoutError(request))

    with pytest.raises(AIProviderTimeoutError):
        await provider.interpret_message(
            InterpretationRequest(message_text="How much U16?", channel="WHATSAPP")
        )


@pytest.mark.asyncio
async def test_openai_provider_maps_authentication_error() -> None:
    provider, _responses = provider_with_response(_status_error(AuthenticationError, 401))

    with pytest.raises(AIProviderAuthenticationError):
        await provider.interpret_message(
            InterpretationRequest(message_text="How much U16?", channel="WHATSAPP")
        )


@pytest.mark.asyncio
async def test_openai_provider_maps_rate_limit() -> None:
    provider, _responses = provider_with_response(_status_error(RateLimitError, 429))

    with pytest.raises(AIProviderRateLimitError):
        await provider.interpret_message(
            InterpretationRequest(message_text="How much U16?", channel="WHATSAPP")
        )


@pytest.mark.asyncio
async def test_openai_provider_maps_server_error() -> None:
    provider, _responses = provider_with_response(_status_error(APIStatusError, 500))

    with pytest.raises(AIProviderRequestError):
        await provider.interpret_message(
            InterpretationRequest(message_text="How much U16?", channel="WHATSAPP")
        )


@pytest.mark.asyncio
async def test_openai_provider_requires_api_key() -> None:
    provider = OpenAIProvider(settings=Settings(openai_model="test-model"))

    with pytest.raises(AIProviderUnavailable):
        await provider.interpret_message(
            InterpretationRequest(message_text="How much U16?", channel="WHATSAPP")
        )


@pytest.mark.asyncio
async def test_openai_provider_requires_model() -> None:
    provider = OpenAIProvider(settings=Settings(openai_api_key="test-api-key"))

    with pytest.raises(AIProviderUnavailable):
        await provider.interpret_message(
            InterpretationRequest(message_text="How much U16?", channel="WHATSAPP")
        )


def _status_error(error_type: type[APIStatusError], status_code: int) -> APIStatusError:
    request = httpx.Request("POST", "https://api.openai.test/responses")
    response = httpx.Response(status_code, request=request)
    return error_type("Synthetic OpenAI error", response=response, body={"error": "synthetic"})


class FakeResponsesResource:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeClient:
    def __init__(self, responses: FakeResponsesResource) -> None:
        self.responses = responses
