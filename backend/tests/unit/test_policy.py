from app.policy.decision_engine import DecisionEngine
from app.policy.escalation import escalation_for_reason
from app.policy.routing import route_reason, route_text
from app.schemas.decision import DecisionContext, KnowledgeEvidence
from app.schemas.enums import (
    DecisionLevel,
    IntentType,
    LanguageCode,
    LanguageMode,
    PICRole,
    ReasonCode,
)
from app.schemas.interpretation import InterpretedMessage, MessageIntent


def interpreted(*intents: MessageIntent) -> InterpretedMessage:
    return InterpretedMessage(
        primary_language=LanguageCode.ENGLISH,
        language_mode=LanguageMode.SINGLE,
        intents=list(intents),
    )


def approved_context(*intent_types: IntentType) -> DecisionContext:
    return DecisionContext(
        evidence=[
            KnowledgeEvidence(
                intent_type=intent_type,
                approved_knowledge_found=True,
                event_data_confirmed=True,
                requires_lookup=False,
                knowledge_source="sample_event_config",
            )
            for intent_type in intent_types
        ]
    )


def test_decision_engine_green_for_complete_approved_rule() -> None:
    result = DecisionEngine().decide(
        interpreted(
            MessageIntent(
                type=IntentType.ELIGIBILITY,
                category="U16",
                entities={"birth_year": 2012},
            )
        ),
        approved_context(IntentType.ELIGIBILITY),
    )

    assert result.level == DecisionLevel.GREEN
    assert result.auto_reply_allowed is True
    assert result.requires_human is False


def test_decision_engine_yellow_for_incomplete_eligibility() -> None:
    result = DecisionEngine().decide(interpreted(MessageIntent(type=IntentType.ELIGIBILITY)))

    assert result.level == DecisionLevel.YELLOW
    assert result.clarification_fields == ["birth_year", "category"]
    assert result.requires_human is False


def test_decision_engine_yellow_for_payment_lookup() -> None:
    result = DecisionEngine().decide(interpreted(MessageIntent(type=IntentType.PAYMENT_STATUS)))

    assert result.level == DecisionLevel.YELLOW
    assert result.reason_code == ReasonCode.PAYMENT_VERIFICATION
    assert result.assigned_pic_role == PICRole.FINANCE


def test_decision_engine_red_for_human_authority() -> None:
    result = DecisionEngine().decide(
        interpreted(MessageIntent(type=IntentType.ELIGIBILITY_EXCEPTION))
    )

    assert result.level == DecisionLevel.RED
    assert result.reason_code == ReasonCode.ELIGIBILITY_EXCEPTION
    assert result.assigned_pic_role == PICRole.COMPETITION
    assert result.requires_human is True


def test_decision_engine_red_when_participant_requests_human() -> None:
    message = interpreted(MessageIntent(type=IntentType.REGISTRATION_INFO))
    message.participant_requested_human = True

    result = DecisionEngine().decide(message)

    assert result.level == DecisionLevel.RED
    assert result.reason_code == ReasonCode.HUMAN_REQUESTED
    assert result.assigned_pic_role == PICRole.GENERAL_ADMIN


def test_decision_engine_red_plus_green_is_red() -> None:
    result = DecisionEngine().decide(
        interpreted(
            MessageIntent(type=IntentType.ELIGIBILITY_EXCEPTION),
            MessageIntent(type=IntentType.FEE),
        ),
        approved_context(IntentType.FEE),
    )

    assert result.level == DecisionLevel.RED
    assert result.reason_code == ReasonCode.ELIGIBILITY_EXCEPTION
    assert result.assigned_pic_role == PICRole.COMPETITION


def test_decision_engine_red_plus_yellow_is_red() -> None:
    result = DecisionEngine().decide(
        interpreted(
            MessageIntent(type=IntentType.REFUND),
            MessageIntent(type=IntentType.PAYMENT_STATUS),
        )
    )

    assert result.level == DecisionLevel.RED
    assert result.reason_code == ReasonCode.REFUND_REQUEST
    assert result.assigned_pic_role == PICRole.FINANCE


def test_decision_engine_yellow_plus_green_is_yellow() -> None:
    result = DecisionEngine().decide(
        interpreted(
            MessageIntent(type=IntentType.PAYMENT_STATUS),
            MessageIntent(type=IntentType.REGISTRATION_INFO),
        ),
        approved_context(IntentType.REGISTRATION_INFO),
    )

    assert result.level == DecisionLevel.YELLOW
    assert result.reason_code == ReasonCode.PAYMENT_VERIFICATION
    assert result.assigned_pic_role == PICRole.FINANCE


def test_decision_engine_green_plus_green_requires_valid_evidence() -> None:
    result = DecisionEngine().decide(
        interpreted(
            MessageIntent(type=IntentType.REGISTRATION_INFO),
            MessageIntent(type=IntentType.FEE),
        ),
        approved_context(IntentType.REGISTRATION_INFO, IntentType.FEE),
    )

    assert result.level == DecisionLevel.GREEN
    assert result.auto_reply_allowed is True


def test_decision_engine_green_with_no_approved_knowledge_is_not_green() -> None:
    result = DecisionEngine().decide(
        interpreted(MessageIntent(type=IntentType.FEE)),
        DecisionContext(
            evidence=[
                KnowledgeEvidence(
                    intent_type=IntentType.FEE,
                    approved_knowledge_found=False,
                    event_data_confirmed=True,
                    requires_lookup=False,
                    knowledge_source="sample_event_config",
                )
            ]
        ),
    )

    assert result.level == DecisionLevel.YELLOW
    assert result.auto_reply_allowed is False
    assert "approved knowledge was not found" in result.notes


def test_decision_engine_green_without_evidence_context_is_not_green() -> None:
    result = DecisionEngine().decide(interpreted(MessageIntent(type=IntentType.FEE)))

    assert result.level == DecisionLevel.YELLOW
    assert result.auto_reply_allowed is False
    assert "no knowledge evidence was provided" in result.notes


def test_decision_engine_green_with_unconfirmed_event_data_is_not_green() -> None:
    result = DecisionEngine().decide(
        interpreted(MessageIntent(type=IntentType.SCHEDULE)),
        DecisionContext(
            evidence=[
                KnowledgeEvidence(
                    intent_type=IntentType.SCHEDULE,
                    approved_knowledge_found=True,
                    event_data_confirmed=False,
                    requires_lookup=False,
                    knowledge_source="sample_event_config",
                )
            ]
        ),
    )

    assert result.level == DecisionLevel.YELLOW
    assert result.auto_reply_allowed is False
    assert "event data is not confirmed" in result.notes


def test_decision_engine_green_with_valid_approved_evidence_is_green() -> None:
    result = DecisionEngine().decide(
        interpreted(MessageIntent(type=IntentType.REGISTRATION_INFO)),
        approved_context(IntentType.REGISTRATION_INFO),
    )

    assert result.level == DecisionLevel.GREEN
    assert result.auto_reply_allowed is True


def test_pic_routing_by_reason_code() -> None:
    assert route_reason(ReasonCode.REGISTRATION_EXCEPTION) == PICRole.REGISTRATION
    assert route_reason(ReasonCode.PAYMENT_VERIFICATION) == PICRole.FINANCE
    assert route_reason(ReasonCode.ELIGIBILITY_EXCEPTION) == PICRole.COMPETITION
    assert route_reason(ReasonCode.SCHEDULE_EXCEPTION) == PICRole.TOURNAMENT_DIRECTOR
    assert route_reason(ReasonCode.MERCHANDISE_ORDER_LOOKUP) == PICRole.MERCHANDISE
    assert route_reason(ReasonCode.COMMERCIAL_ENQUIRY) == PICRole.COMMERCIAL
    assert route_reason(None) == PICRole.GENERAL_ADMIN


def test_pic_routing_by_text() -> None:
    assert route_text("late registration") == PICRole.REGISTRATION
    assert route_text("overpayment issue") == PICRole.FINANCE
    assert route_text("rule dispute") == PICRole.COMPETITION
    assert route_text("walkover appeal") == PICRole.TOURNAMENT_DIRECTOR
    assert route_text("venue / operations issue") == PICRole.OPERATIONS
    assert route_text("merchandise issue") == PICRole.MERCHANDISE
    assert route_text("vendor booth enquiry") == PICRole.COMMERCIAL
    assert route_text("something unclear") == PICRole.GENERAL_ADMIN


def test_escalation_mapping() -> None:
    refund = escalation_for_reason(ReasonCode.REFUND_REQUEST)
    payment = escalation_for_reason(ReasonCode.PAYMENT_VERIFICATION)

    assert refund.decision_level == DecisionLevel.RED
    assert refund.requires_human is True
    assert refund.pic_role == PICRole.FINANCE
    assert payment.decision_level == DecisionLevel.YELLOW
    assert payment.requires_human is False
