import pytest

from app.ai.base import (
    AIProviderCallMetadata,
    GeneratedResponse,
    ResponseGenerationRequest,
)
from app.ai.responder import ResponseGenerator
from app.schemas.decision import DecisionResult
from app.schemas.enums import DecisionLevel, IntentType, LanguageCode, LanguageMode
from app.schemas.interpretation import InterpretationRequest, InterpretedMessage, MessageIntent


class DraftProvider:
    provider_name = "draft-test"
    model = "draft-test"

    def __init__(self) -> None:
        self.interpretation_metadata: AIProviderCallMetadata | None = None
        self.response_metadata: AIProviderCallMetadata | None = AIProviderCallMetadata(
            provider_request_id="stale-response"
        )
        self.response_calls = 0

    async def interpret_message(self, request: InterpretationRequest) -> InterpretedMessage:
        raise AssertionError("interpret_message is not used by ResponseGenerator tests")

    async def generate_response(self, request: ResponseGenerationRequest) -> GeneratedResponse:
        self.response_calls += 1
        self.response_metadata = AIProviderCallMetadata(provider_request_id="provider-response")
        return GeneratedResponse(
            text="  I'll forward your request and get back to you as soon as possible.  ",
            should_send=True,
        )


def _request(*, language: LanguageCode, requires_human: bool) -> ResponseGenerationRequest:
    return ResponseGenerationRequest(
        interpreted_message=InterpretedMessage(
            primary_language=language,
            language_mode=LanguageMode.SINGLE,
            intents=[MessageIntent(type=IntentType.UNKNOWN)],
        ),
        decision_result=DecisionResult(
            level=DecisionLevel.RED if requires_human else DecisionLevel.GREEN,
            auto_reply_allowed=not requires_human,
            requires_human=requires_human,
        ),
        response_language=language.value,
        participant_text="Synthetic owner test",
    )


@pytest.mark.parametrize(
    ("language", "expected_text"),
    [
        (
            LanguageCode.ENGLISH,
            "Thanks for checking. This needs review by our team before we can confirm anything.",
        ),
        (
            LanguageCode.MALAY,
            "Terima kasih bertanya. Perkara ini perlu disemak oleh pasukan kami sebelum kami "
            "boleh sahkan apa-apa.",
        ),
        (LanguageCode.MANDARIN, "谢谢你的询问。这需要由我们的团队审核后才能确认。"),
    ],
)
async def test_human_required_decision_uses_deterministic_safe_draft(
    language: LanguageCode,
    expected_text: str,
) -> None:
    provider = DraftProvider()
    generator = ResponseGenerator(provider)

    response = await generator.generate(_request(language=language, requires_human=True))

    assert response.text == expected_text
    assert response.should_send is False
    assert provider.response_calls == 0
    assert provider.response_metadata is None
    assert "forward" not in response.text.lower()
    assert "get back" not in response.text.lower()


async def test_non_human_decision_keeps_provider_draft_but_never_send_permission() -> None:
    provider = DraftProvider()
    generator = ResponseGenerator(provider)

    response = await generator.generate(
        _request(language=LanguageCode.ENGLISH, requires_human=False)
    )

    assert response.text == "I'll forward your request and get back to you as soon as possible."
    assert response.should_send is False
    assert provider.response_calls == 1
    assert provider.response_metadata is not None
    assert provider.response_metadata.provider_request_id == "provider-response"
