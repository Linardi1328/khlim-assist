import pytest
from app.ai.base import (
    AIProviderCallMetadata,
    GeneratedResponse,
    ResponseGenerationRequest,
)
from app.ai.responder import ResponseGenerator
from app.schemas.decision import DecisionResult
from app.schemas.enums import DecisionLevel, IntentType, KnowledgeTopic, LanguageCode, LanguageMode
from app.schemas.interpretation import InterpretationRequest, InterpretedMessage, MessageIntent
from app.schemas.retrieval import KnowledgeResult


class DraftProvider:
    provider_name = "draft-test"
    model = "draft-test"

    def __init__(self, text: str = "Unused provider draft") -> None:
        self.interpretation_metadata: AIProviderCallMetadata | None = None
        self.response_metadata: AIProviderCallMetadata | None = AIProviderCallMetadata(
            provider_request_id="stale-response"
        )
        self.response_calls = 0
        self.text = text

    async def interpret_message(self, request: InterpretationRequest) -> InterpretedMessage:
        raise AssertionError("interpret_message is not used by ResponseGenerator tests")

    async def generate_response(self, request: ResponseGenerationRequest) -> GeneratedResponse:
        self.response_calls += 1
        self.response_metadata = AIProviderCallMetadata(provider_request_id="provider-response")
        return GeneratedResponse(text=self.text, should_send=True)


def _request(
    *,
    language: LanguageCode,
    requires_human: bool,
    intent_type: IntentType = IntentType.UNKNOWN,
    category: str | None = None,
    knowledge_results: list[KnowledgeResult] | None = None,
) -> ResponseGenerationRequest:
    return ResponseGenerationRequest(
        interpreted_message=InterpretedMessage(
            primary_language=language,
            language_mode=LanguageMode.SINGLE,
            intents=[MessageIntent(type=intent_type, category=category)],
        ),
        decision_result=DecisionResult(
            level=DecisionLevel.RED if requires_human else DecisionLevel.GREEN,
            auto_reply_allowed=not requires_human,
            requires_human=requires_human,
        ),
        knowledge_results=knowledge_results or [],
        response_language=language.value,
        participant_text="Synthetic owner test",
    )


def _fee_knowledge(value: object = None) -> KnowledgeResult:
    return KnowledgeResult(
        intent_type=IntentType.FEE,
        knowledge_topic=KnowledgeTopic.CATEGORY_FEE,
        found=True,
        source_type="event_rule",
        source_identifier="synthetic-fee-rule",
        rule_type="registration_fee",
        value={"amount_myr": 180} if value is None else value,
        confirmed=True,
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


async def test_non_human_decision_keeps_grounded_provider_draft_but_never_send_permission() -> None:
    provider = DraftProvider("  The U16 registration fee is RM180.  ")
    generator = ResponseGenerator(provider)

    response = await generator.generate(
        _request(
            language=LanguageCode.ENGLISH,
            requires_human=False,
            intent_type=IntentType.FEE,
            category="U16",
            knowledge_results=[_fee_knowledge()],
        )
    )

    assert response.text == "The U16 registration fee is RM180."
    assert response.should_send is False
    assert provider.response_calls == 1
    assert provider.response_metadata is not None
    assert provider.response_metadata.provider_request_id == "provider-response"


async def test_non_human_draft_removes_unsupported_policy_sentence() -> None:
    provider = DraftProvider(
        "The registration fee for the U16 category is RM180. "
        "This fee is set by the event rules and can't be changed. "
        "If you have any other questions, feel free to let me know!"
    )
    generator = ResponseGenerator(provider)

    response = await generator.generate(
        _request(
            language=LanguageCode.ENGLISH,
            requires_human=False,
            intent_type=IntentType.FEE,
            category="U16",
            knowledge_results=[_fee_knowledge()],
        )
    )

    assert response.text == (
        "The registration fee for the U16 category is RM180. "
        "If you have any other questions, feel free to let me know!"
    )
    assert "can't be changed" not in response.text.lower()
    assert "RM180" in response.text
    assert response.should_send is False


async def test_non_human_draft_removes_unperformed_handoff_promise() -> None:
    provider = DraftProvider(
        "The U16 registration fee is RM180. I'll forward this to the team and get back to you."
    )
    generator = ResponseGenerator(provider)

    response = await generator.generate(
        _request(
            language=LanguageCode.ENGLISH,
            requires_human=False,
            intent_type=IntentType.FEE,
            category="U16",
            knowledge_results=[_fee_knowledge()],
        )
    )

    assert response.text == "The U16 registration fee is RM180."
    assert "forward" not in response.text.lower()
    assert "get back" not in response.text.lower()
    assert response.should_send is False


async def test_policy_wording_is_kept_when_explicitly_present_in_approved_evidence() -> None:
    approved = "The U16 fee is RM180 and cannot be changed."
    provider = DraftProvider(approved)
    generator = ResponseGenerator(provider)

    response = await generator.generate(
        _request(
            language=LanguageCode.ENGLISH,
            requires_human=False,
            intent_type=IntentType.FEE,
            category="U16",
            knowledge_results=[_fee_knowledge(approved)],
        )
    )

    assert response.text == approved
    assert response.should_send is False


async def test_all_removed_provider_text_falls_back_to_confirmed_fee_evidence() -> None:
    provider = DraftProvider("I'll forward this to the team and get back to you.")
    generator = ResponseGenerator(provider)

    response = await generator.generate(
        _request(
            language=LanguageCode.ENGLISH,
            requires_human=False,
            intent_type=IntentType.FEE,
            category="U16",
            knowledge_results=[_fee_knowledge()],
        )
    )

    assert response.text == "The approved registration fee for U16 is RM180."
    assert response.should_send is False
