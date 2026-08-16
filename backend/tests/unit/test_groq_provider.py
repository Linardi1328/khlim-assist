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
from app.ai.groq_client import GroqProvider
from app.config.settings import Settings
from app.schemas.decision import DecisionResult
from app.schemas.enums import DecisionLevel, IntentType
from app.schemas.interpretation import InterpretationRequest, InterpretedMessage, MessageIntent
from app.schemas.retrieval import KnowledgeResult
from openai import APIStatusError, APITimeoutError, AuthenticationError, RateLimitError


def response_with_text(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        output_text=text,
        id="resp_groq_synthetic",
        usage=SimpleNamespace(input_tokens=11, output_tokens=7, total_tokens=18),
    )


def provider_with_response(response: object) -> tuple[GroqProvider, "FakeResponsesResource"]:
    responses = FakeResponsesResource(response=response)
    provider = GroqProvider(
        settings=Settings(groq_api_key="test-groq-key", groq_model="openai/gpt-oss-120b"),
        client=FakeClient(responses),
    )
    return provider, responses


@pytest.mark.asyncio
async def test_groq_provider_requires_api_key() -> None:
    provider = GroqProvider(settings=Settings(groq_api_key="", groq_model="test-model"))

    with pytest.raises(AIProviderUnavailable) as exc_info:
        await provider.interpret_message(
            InterpretationRequest(message_text="How much U16?", channel="WHATSAPP")
        )

    assert "GROQ_API_KEY" in str(exc_info.value)


@pytest.mark.asyncio
async def test_groq_provider_requires_model() -> None:
    provider = GroqProvider(settings=Settings(groq_api_key="test-groq-key", groq_model=""))

    with pytest.raises(AIProviderUnavailable) as exc_info:
        await provider.interpret_message(
            InterpretationRequest(message_text="How much U16?", channel="WHATSAPP")
        )

    assert "GROQ_MODEL" in str(exc_info.value)


def test_groq_provider_constructs_client_with_configured_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = FakeResponsesResource(response=response_with_text("{}"))
    fake_client = FakeClient(responses)
    created: dict[str, object] = {}

    def fake_async_openai(**kwargs: object) -> FakeClient:
        created.update(kwargs)
        return fake_client

    monkeypatch.setattr("app.ai.groq_client.AsyncOpenAI", fake_async_openai)
    provider = GroqProvider(
        settings=Settings(
            groq_api_key="test-groq-key",
            groq_model="configured-model",
            groq_api_base_url="https://groq.test/openai/v1",
        )
    )

    assert provider.client is fake_client
    assert created["api_key"] == "test-groq-key"
    assert created["base_url"] == "https://groq.test/openai/v1"


@pytest.mark.asyncio
async def test_groq_provider_successful_structured_interpretation() -> None:
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
    call = responses.calls[0]
    assert call["model"] == "openai/gpt-oss-120b"
    assert "store" not in call
    assert "temperature" not in call
    assert "previous_response_id" not in call
    assert call["background"] is False
    assert call["tools"] == []
    text_config = call["text"]
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
    intent_properties = intent_schema["properties"]
    for field_name in ("category", "knowledge_topic", "reason_code"):
        nullable_field = intent_properties[field_name]
        assert "anyOf" not in nullable_field
        assert nullable_field["type"] == ["string", "null"]
    assert None in intent_properties["knowledge_topic"]["enum"]
    assert None in intent_properties["reason_code"]["enum"]
    entities_schema = intent_properties["entities"]
    assert entities_schema["additionalProperties"] is False
    for entity_schema in entities_schema["properties"].values():
        assert "anyOf" not in entity_schema
        assert "null" in entity_schema["type"]
    assert provider.interpretation_metadata is not None
    assert provider.interpretation_metadata.provider_request_id == "resp_groq_synthetic"
    assert provider.interpretation_metadata.total_tokens == 18


@pytest.mark.asyncio
async def test_groq_provider_successful_response_generation() -> None:
    provider, responses = provider_with_response(response_with_text("Hi! Approved draft."))

    generated = await provider.generate_response(_response_generation_request())

    assert generated.text == "Hi! Approved draft."
    assert generated.should_send is False
    call = responses.calls[0]
    assert call["model"] == "openai/gpt-oss-120b"
    assert "store" not in call
    assert "temperature" not in call
    assert "previous_response_id" not in call
    assert call["background"] is False
    assert call["tools"] == []
    assert provider.response_metadata is not None
    assert provider.response_metadata.total_tokens == 18


@pytest.mark.asyncio
async def test_groq_provider_rejects_malformed_interpretation() -> None:
    provider, _responses = provider_with_response(response_with_text('{"primary_language":"en"}'))

    with pytest.raises(AIProviderResponseError):
        await provider.interpret_message(
            InterpretationRequest(message_text="How much U16?", channel="WHATSAPP")
        )


@pytest.mark.asyncio
async def test_groq_provider_maps_authentication_error_without_exposing_key() -> None:
    key = "test-groq-secret-key"
    provider = GroqProvider(
        settings=Settings(groq_api_key=key, groq_model="test-model"),
        client=FakeClient(
            FakeResponsesResource(
                _status_error(AuthenticationError, 401, body={"authorization": key})
            )
        ),
    )

    with pytest.raises(AIProviderAuthenticationError) as exc_info:
        await provider.interpret_message(
            InterpretationRequest(message_text="How much U16?", channel="WHATSAPP")
        )

    assert key not in str(exc_info.value)
    assert "Groq" in str(exc_info.value)


@pytest.mark.asyncio
async def test_groq_provider_maps_rate_limit_without_exposing_key() -> None:
    key = "test-groq-secret-key"
    provider = GroqProvider(
        settings=Settings(groq_api_key=key, groq_model="test-model"),
        client=FakeClient(
            FakeResponsesResource(_status_error(RateLimitError, 429, body={"api_key": key}))
        ),
    )

    with pytest.raises(AIProviderRateLimitError) as exc_info:
        await provider.interpret_message(
            InterpretationRequest(message_text="How much U16?", channel="WHATSAPP")
        )

    assert key not in str(exc_info.value)
    assert "Groq" in str(exc_info.value)


@pytest.mark.asyncio
async def test_groq_provider_maps_timeout() -> None:
    request = httpx.Request("POST", "https://api.groq.test/openai/v1/responses")
    provider, _responses = provider_with_response(APITimeoutError(request))

    with pytest.raises(AIProviderTimeoutError):
        await provider.interpret_message(
            InterpretationRequest(message_text="How much U16?", channel="WHATSAPP")
        )


@pytest.mark.asyncio
async def test_groq_provider_maps_other_api_errors_without_exposing_key() -> None:
    key = "test-groq-secret-key"
    provider = GroqProvider(
        settings=Settings(groq_api_key=key, groq_model="test-model"),
        client=FakeClient(
            FakeResponsesResource(_status_error(APIStatusError, 500, body={"api_key": key}))
        ),
    )

    with pytest.raises(AIProviderRequestError) as exc_info:
        await provider.interpret_message(
            InterpretationRequest(message_text="How much U16?", channel="WHATSAPP")
        )

    assert key not in str(exc_info.value)
    assert "Groq request failed with status 500" in str(exc_info.value)


def _response_generation_request() -> ResponseGenerationRequest:
    return ResponseGenerationRequest(
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


def _status_error(
    error_type: type[APIStatusError],
    status_code: int,
    *,
    body: object | None = None,
) -> APIStatusError:
    request = httpx.Request("POST", "https://api.groq.test/openai/v1/responses")
    response = httpx.Response(status_code, request=request)
    return error_type("Synthetic Groq error", response=response, body=body or {})


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
