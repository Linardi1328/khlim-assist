from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from app.schemas.conversations import ConversationCreate
from app.schemas.enums import (
    AnswerSource,
    ChannelName,
    ConversationState,
    EventStatus,
    FAQCategory,
    FAQDisposition,
    FAQStatus,
    IntentType,
    LanguageCode,
    LanguageMode,
    RuleStatus,
)
from app.schemas.events import EventCreate
from app.schemas.faq import FAQEntryCreate, FAQSeedEntry
from app.schemas.interpretation import InterpretedMessage, MessageIntent
from app.schemas.rules import EventRuleCreate
from pydantic import ValidationError


def test_event_schema_validates_dates() -> None:
    event = EventCreate(
        slug="sample-event",
        name="Sample Event",
        status=EventStatus.PUBLISHED,
        start_date=date(2027, 6, 12),
        end_date=date(2027, 6, 13),
        registration_deadline=datetime(2027, 5, 31, 23, 59, tzinfo=UTC),
        registration_url="https://example.com/register",
    )

    assert event.slug == "sample-event"


def test_event_schema_rejects_invalid_date_order() -> None:
    with pytest.raises(ValidationError):
        EventCreate(
            slug="bad-event",
            name="Bad Event",
            start_date=date(2027, 6, 13),
            end_date=date(2027, 6, 12),
        )


def test_faq_schema_rejects_human_auto_reply() -> None:
    with pytest.raises(ValidationError):
        FAQEntryCreate(
            faq_key="refund",
            category=FAQCategory.PAYMENT,
            generalized_question="Can I get a refund?",
            answer_source=AnswerSource.HUMAN_PIC,
            auto_reply_allowed=True,
            requires_human=True,
            status=FAQStatus.APPROVED,
        )


def test_faq_seed_disposition_flags() -> None:
    entry = FAQSeedEntry(
        faq_key="registration_link",
        category=FAQCategory.REGISTRATION,
        generalized_question="Where do I register?",
        normal_disposition=FAQDisposition.AUTO,
        answer_source=AnswerSource.EVENT_CONFIG,
        auto_reply_allowed=True,
        requires_lookup=False,
        requires_human=False,
    )

    assert entry.normal_disposition == FAQDisposition.AUTO


def test_event_rule_schema_supports_structured_json_value() -> None:
    event_id = uuid4()
    rule = EventRuleCreate(
        event_id=event_id,
        category="U16",
        rule_type="minimum_birth_year",
        value={"birth_year": 2011},
        status=RuleStatus.ACTIVE,
    )

    assert rule.value["birth_year"] == 2011


def test_conversation_states_include_required_lifecycle() -> None:
    states = {state.value for state in ConversationState}

    assert {
        "AI_ACTIVE",
        "WAITING_FOR_CLARIFICATION",
        "HUMAN_REQUIRED",
        "HUMAN_ACTIVE",
        "RESOLVED",
    }.issubset(states)


def test_conversation_schema_accepts_human_takeover_state() -> None:
    conversation = ConversationCreate(
        channel=ChannelName.WHATSAPP,
        external_user_ref="anon_user",
        preferred_language=LanguageCode.MIXED,
        state=ConversationState.HUMAN_REQUIRED,
        human_takeover=True,
    )

    assert conversation.human_takeover is True


def test_multi_intent_interpretation_schema() -> None:
    interpreted = InterpretedMessage(
        primary_language=LanguageCode.MIXED,
        language_mode=LanguageMode.MIXED,
        intents=[
            MessageIntent(type=IntentType.SCHEDULE, category="U16"),
            MessageIntent(type=IntentType.TEAM_COMPOSITION, entities={"maximum_players": 4}),
            MessageIntent(type=IntentType.ELIGIBILITY, entities={"foreign_player": True}),
        ],
    )

    assert [intent.type for intent in interpreted.intents] == [
        IntentType.SCHEDULE,
        IntentType.TEAM_COMPOSITION,
        IntentType.ELIGIBILITY,
    ]


def test_interpretation_requires_clarification_fields_when_flagged() -> None:
    with pytest.raises(ValidationError):
        InterpretedMessage(
            primary_language=LanguageCode.ENGLISH,
            language_mode=LanguageMode.SINGLE,
            intents=[MessageIntent(type=IntentType.ELIGIBILITY)],
            requires_clarification=True,
        )
