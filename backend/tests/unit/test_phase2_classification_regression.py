import pytest
from pydantic import ValidationError

from app.ai.fake import FakeAIProvider
from app.policy.decision_engine import DecisionEngine
from app.schemas.decision import DecisionContext, KnowledgeEvidence
from app.schemas.enums import DecisionLevel, IntentType, LanguageCode, LanguageMode
from app.schemas.interpretation import InterpretationRequest


@pytest.mark.parametrize(
    ("text", "language", "mode", "intents", "level"),
    [
        (
            "How much is U16?",
            LanguageCode.ENGLISH,
            LanguageMode.SINGLE,
            [IntentType.FEE],
            DecisionLevel.GREEN,
        ),
        (
            "Have you received my payment?",
            LanguageCode.ENGLISH,
            LanguageMode.SINGLE,
            [IntentType.PAYMENT_STATUS],
            DecisionLevel.YELLOW,
        ),
        (
            "My player is one month overage, can make exception?",
            LanguageCode.ENGLISH,
            LanguageMode.SINGLE,
            [IntentType.ELIGIBILITY_EXCEPTION],
            DecisionLevel.RED,
        ),
        (
            "Pendaftaran masih buka ke?",
            LanguageCode.MALAY,
            LanguageMode.SINGLE,
            [IntentType.REGISTRATION_INFO],
            DecisionLevel.GREEN,
        ),
        (
            "Payment saya sudah masuk ke?",
            LanguageCode.MALAY,
            LanguageMode.SINGLE,
            [IntentType.PAYMENT_STATUS],
            DecisionLevel.YELLOW,
        ),
        (
            "Boleh daftar lambat sikit tak?",
            LanguageCode.MALAY,
            LanguageMode.SINGLE,
            [IntentType.LATE_REGISTRATION],
            DecisionLevel.RED,
        ),
        (
            "报名费是多少？",
            LanguageCode.MANDARIN,
            LanguageMode.SINGLE,
            [IntentType.FEE],
            DecisionLevel.GREEN,
        ),
        (
            "你们收到我的付款了吗？",
            LanguageCode.MANDARIN,
            LanguageMode.SINGLE,
            [IntentType.PAYMENT_STATUS],
            DecisionLevel.YELLOW,
        ),
        (
            "如果退出可以退款吗？",
            LanguageCode.MANDARIN,
            LanguageMode.SINGLE,
            [IntentType.WITHDRAWAL, IntentType.REFUND],
            DecisionLevel.RED,
        ),
        (
            "coach 2012 可以打 u16 吗",
            LanguageCode.MIXED,
            LanguageMode.MIXED,
            [IntentType.ELIGIBILITY],
            DecisionLevel.GREEN,
        ),
        (
            "coach can check payment sudah receive?",
            LanguageCode.MIXED,
            LanguageMode.MIXED,
            [IntentType.PAYMENT_STATUS],
            DecisionLevel.YELLOW,
        ),
        (
            "I terbayar extra, can refund balance?",
            LanguageCode.MIXED,
            LanguageMode.MIXED,
            [IntentType.OVERPAYMENT, IntentType.REFUND],
            DecisionLevel.RED,
        ),
    ],
    ids=[
        "english-green",
        "english-yellow",
        "english-red",
        "malay-green",
        "malay-yellow",
        "malay-red",
        "mandarin-green",
        "mandarin-yellow",
        "mandarin-red",
        "mixed-green",
        "mixed-yellow",
        "mixed-red",
    ],
)
async def test_multilingual_classification_regression(
    text: str,
    language: LanguageCode,
    mode: LanguageMode,
    intents: list[IntentType],
    level: DecisionLevel,
) -> None:
    interpreted = await FakeAIProvider().interpret_message(
        InterpretationRequest(message_text=text, channel="regression")
    )
    context = DecisionContext(
        evidence=[
            KnowledgeEvidence(
                intent_type=intent.type,
                approved_knowledge_found=True,
                event_data_confirmed=True,
                knowledge_source="deterministic-regression-fixture",
                confirmed=True,
            )
            for intent in interpreted.intents
        ]
    )
    decision = DecisionEngine().decide(interpreted, context)

    assert interpreted.primary_language == language
    assert interpreted.language_mode == mode
    assert [intent.type for intent in interpreted.intents] == intents
    assert decision.level == level
    assert decision.auto_reply_allowed is (level == DecisionLevel.GREEN)
    assert decision.requires_human is (level == DecisionLevel.RED)


@pytest.mark.parametrize("text", [" ", "\t", "\n", "!!!", "\x00\ufffd"])
async def test_blank_or_malformed_text_fails_closed_as_red(text: str) -> None:
    request = InterpretationRequest(message_text=text, channel="regression")

    first = await FakeAIProvider().interpret_message(request)
    second = await FakeAIProvider().interpret_message(request)
    first_decision = DecisionEngine().decide(first)
    second_decision = DecisionEngine().decide(second)

    assert first == second
    assert [intent.type for intent in first.intents] == [IntentType.UNKNOWN]
    assert first_decision == second_decision
    assert first_decision.level == DecisionLevel.RED
    assert first_decision.auto_reply_allowed is False
    assert first_decision.requires_human is True


@pytest.mark.parametrize("message_text", ["", None, 123, [], {}])
def test_empty_or_non_text_input_is_rejected(message_text: object) -> None:
    with pytest.raises(ValidationError):
        InterpretationRequest.model_validate(
            {"message_text": message_text, "channel": "regression"}
        )
