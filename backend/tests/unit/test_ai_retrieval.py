from datetime import UTC, date, datetime

from app.ai.retrieval import SQLKnowledgeRetriever, results_to_decision_context
from app.config.settings import Settings
from app.db.models.conversation import Conversation
from app.db.models.event import Event
from app.db.models.event_rule import EventRule
from app.db.models.faq_entry import FAQEntry
from app.policy.decision_engine import DecisionEngine
from app.schemas.enums import (
    AnswerSource,
    ChannelName,
    DecisionLevel,
    EventStatus,
    FAQCategory,
    FAQStatus,
    IntentType,
    KnowledgeTopic,
    PICRole,
    RuleStatus,
)
from app.schemas.interpretation import InterpretedMessage, MessageIntent
from app.schemas.retrieval import KnowledgeQuery
from sqlalchemy.ext.asyncio import AsyncSession


def interpreted(*intents: MessageIntent) -> InterpretedMessage:
    return InterpretedMessage(
        primary_language="en",
        language_mode="single",
        intents=list(intents),
    )


async def create_event(db_session: AsyncSession, slug: str, active: bool = True) -> Event:
    event = Event(
        slug=slug,
        name=f"Synthetic {slug}",
        status=EventStatus.PUBLISHED,
        venue="Synthetic Venue",
        start_date=date(2027, 6, 12),
        end_date=date(2027, 6, 13),
        registration_open=True,
        registration_deadline=datetime(2027, 5, 31, 23, 59, tzinfo=UTC),
        registration_url="https://example.com/register",
        is_active=active,
    )
    db_session.add(event)
    await db_session.flush()
    return event


async def add_rule(
    db_session: AsyncSession,
    event: Event,
    category: str,
    rule_type: str,
    value: dict[str, object],
) -> None:
    db_session.add(
        EventRule(
            event_id=event.id,
            category=category,
            rule_type=rule_type,
            value=value,
            status=RuleStatus.ACTIVE,
        )
    )
    await db_session.flush()


async def add_faq(
    db_session: AsyncSession,
    *,
    faq_key: str,
    category: FAQCategory,
    static_answer: str,
    event: Event | None = None,
) -> None:
    db_session.add(
        FAQEntry(
            event_id=event.id if event else None,
            faq_key=faq_key,
            category=category,
            generalized_question=f"Synthetic question for {faq_key}",
            answer_source=AnswerSource.EVENT_CONFIG,
            static_answer=static_answer,
            auto_reply_allowed=True,
            requires_lookup=False,
            requires_human=False,
            status=FAQStatus.APPROVED,
        )
    )
    await db_session.flush()


async def test_green_fee_requires_active_event_rule(db_session: AsyncSession) -> None:
    event = await create_event(db_session, "fee-event")
    await add_rule(db_session, event, "U16", "registration_fee", {"amount_myr": 180})
    message = interpreted(
        MessageIntent(
            type=IntentType.FEE,
            category="U16",
            knowledge_topic=KnowledgeTopic.REGISTRATION_FEE,
        )
    )

    results = await SQLKnowledgeRetriever(Settings(active_event_id=event.id)).retrieve(
        db_session,
        KnowledgeQuery(interpreted_message=message),
    )
    decision = DecisionEngine().decide(message, results_to_decision_context(results))

    assert results[0].found is True
    assert results[0].source_type == "event_rule"
    assert decision.level == DecisionLevel.GREEN


async def test_green_intent_without_active_event_is_not_green(db_session: AsyncSession) -> None:
    message = interpreted(
        MessageIntent(
            type=IntentType.FEE,
            category="U16",
            knowledge_topic=KnowledgeTopic.REGISTRATION_FEE,
        )
    )

    results = await SQLKnowledgeRetriever(Settings(active_event_id=None)).retrieve(
        db_session,
        KnowledgeQuery(interpreted_message=message),
    )
    decision = DecisionEngine().decide(message, results_to_decision_context(results))

    assert results[0].found is False
    assert decision.level == DecisionLevel.YELLOW


async def test_conversation_event_preferred_over_active_event(db_session: AsyncSession) -> None:
    active_event = await create_event(db_session, "active-event")
    conversation_event = await create_event(db_session, "conversation-event")
    await add_rule(db_session, active_event, "U16", "registration_fee", {"amount_myr": 999})
    await add_rule(db_session, conversation_event, "U16", "registration_fee", {"amount_myr": 180})
    conversation = Conversation(
        channel=ChannelName.WHATSAPP,
        external_user_ref="15550000001",
        event_id=conversation_event.id,
    )
    db_session.add(conversation)
    await db_session.flush()
    message = interpreted(
        MessageIntent(
            type=IntentType.FEE,
            category="U16",
            knowledge_topic=KnowledgeTopic.REGISTRATION_FEE,
        )
    )

    results = await SQLKnowledgeRetriever(Settings(active_event_id=active_event.id)).retrieve(
        db_session,
        KnowledgeQuery(interpreted_message=message, conversation_id=conversation.id),
    )

    assert results[0].event_id == conversation_event.id
    assert results[0].value == {"amount_myr": 180}


async def test_lookup_and_human_policy_evidence_routes_safely(
    db_session: AsyncSession,
) -> None:
    payment = interpreted(MessageIntent(type=IntentType.PAYMENT_STATUS))
    refund = interpreted(MessageIntent(type=IntentType.REFUND))
    retriever = SQLKnowledgeRetriever(Settings())

    payment_results = await retriever.retrieve(
        db_session,
        KnowledgeQuery(interpreted_message=payment),
    )
    refund_results = await retriever.retrieve(
        db_session,
        KnowledgeQuery(interpreted_message=refund),
    )
    payment_decision = DecisionEngine().decide(
        payment,
        results_to_decision_context(payment_results),
    )
    refund_decision = DecisionEngine().decide(
        refund,
        results_to_decision_context(refund_results),
    )

    assert payment_results[0].requires_lookup is True
    assert payment_decision.level == DecisionLevel.YELLOW
    assert payment_decision.assigned_pic_role == PICRole.FINANCE
    assert refund_results[0].requires_human is True
    assert refund_decision.level == DecisionLevel.RED
    assert refund_decision.assigned_pic_role == PICRole.FINANCE


async def test_multi_intent_retrieval_allows_green_when_all_evidence_exists(
    db_session: AsyncSession,
) -> None:
    event = await create_event(db_session, "multi-event")
    await add_rule(db_session, event, "U16", "category_playing_date", {"date": "2027-06-13"})
    await add_rule(db_session, event, "GENERAL", "player_count", {"minimum": 3, "maximum": 4})
    await add_rule(
        db_session,
        event,
        "GENERAL",
        "foreign_player_policy",
        {"permitted": True, "maximum_foreign_players": 1},
    )
    message = interpreted(
        MessageIntent(
            type=IntentType.SCHEDULE,
            category="U16",
            knowledge_topic=KnowledgeTopic.CATEGORY_PLAYING_DATE,
        ),
        MessageIntent(
            type=IntentType.TEAM_COMPOSITION,
            knowledge_topic=KnowledgeTopic.TEAM_MAX_PLAYERS,
            entities={"maximum_players": 4},
        ),
        MessageIntent(
            type=IntentType.ELIGIBILITY,
            knowledge_topic=KnowledgeTopic.FOREIGN_PLAYERS_ALLOWED,
            entities={"foreign_player": True},
        ),
    )

    results = await SQLKnowledgeRetriever(Settings(active_event_id=event.id)).retrieve(
        db_session,
        KnowledgeQuery(interpreted_message=message),
    )
    decision = DecisionEngine().decide(message, results_to_decision_context(results))

    assert [result.found for result in results] == [True, True, True]
    assert decision.level == DecisionLevel.GREEN


async def test_fees_faq_collision_does_not_answer_early_bird_deadline_from_fee(
    db_session: AsyncSession,
) -> None:
    event = await create_event(db_session, "fees-collision-event")
    await add_faq(
        db_session,
        faq_key="fees_registration_fee",
        category=FAQCategory.FEES,
        static_answer="Synthetic registration fee answer.",
        event=event,
    )
    await add_faq(
        db_session,
        faq_key="fees_early_bird_end",
        category=FAQCategory.FEES,
        static_answer="Synthetic early-bird deadline answer.",
        event=event,
    )
    message = interpreted(
        MessageIntent(
            type=IntentType.EARLY_BIRD,
            category="U16",
            knowledge_topic=KnowledgeTopic.EARLY_BIRD_DEADLINE,
        )
    )

    results = await SQLKnowledgeRetriever(Settings(active_event_id=event.id)).retrieve(
        db_session,
        KnowledgeQuery(interpreted_message=message),
    )

    assert results[0].faq_key == "fees_early_bird_end"
    assert results[0].faq_key != "fees_registration_fee"
    assert results[0].value == "Synthetic early-bird deadline answer."


async def test_player_count_rule_collision_returns_maximum_rule(
    db_session: AsyncSession,
) -> None:
    event = await create_event(db_session, "players-collision-event")
    await add_rule(db_session, event, "GENERAL", "minimum_players", {"minimum": 3})
    await add_rule(db_session, event, "GENERAL", "maximum_players", {"maximum": 4})
    message = interpreted(
        MessageIntent(
            type=IntentType.TEAM_COMPOSITION,
            knowledge_topic=KnowledgeTopic.TEAM_MAX_PLAYERS,
            entities={"maximum_players": 4},
        )
    )

    results = await SQLKnowledgeRetriever(Settings(active_event_id=event.id)).retrieve(
        db_session,
        KnowledgeQuery(interpreted_message=message),
    )

    assert results[0].rule_type == "maximum_players"
    assert results[0].value == {"maximum": 4}


async def test_early_bird_rule_collision_does_not_return_registration_fee(
    db_session: AsyncSession,
) -> None:
    event = await create_event(db_session, "early-bird-rule-event")
    await add_rule(db_session, event, "U16", "registration_fee", {"amount_myr": 220})
    await add_rule(db_session, event, "U16", "early_bird_fee", {"amount_myr": 180})
    message = interpreted(
        MessageIntent(
            type=IntentType.EARLY_BIRD,
            category="U16",
            knowledge_topic=KnowledgeTopic.EARLY_BIRD_FEE,
        )
    )

    results = await SQLKnowledgeRetriever(Settings(active_event_id=event.id)).retrieve(
        db_session,
        KnowledgeQuery(interpreted_message=message),
    )

    assert results[0].rule_type == "early_bird_fee"
    assert results[0].value == {"amount_myr": 180}


async def test_player_restriction_collision_returns_national_policy(
    db_session: AsyncSession,
) -> None:
    event = await create_event(db_session, "restriction-collision-event")
    await add_rule(db_session, event, "GENERAL", "foreign_player_policy", {"permitted": True})
    await add_rule(
        db_session,
        event,
        "GENERAL",
        "national_player_policy",
        {"national_players_permitted": False},
    )
    message = interpreted(
        MessageIntent(
            type=IntentType.PLAYER_RESTRICTIONS,
            knowledge_topic=KnowledgeTopic.NATIONAL_PLAYER_POLICY,
            entities={"national_player": True},
        )
    )

    results = await SQLKnowledgeRetriever(Settings(active_event_id=event.id)).retrieve(
        db_session,
        KnowledgeQuery(interpreted_message=message),
    )

    assert results[0].rule_type == "national_player_policy"
    assert results[0].value == {"national_players_permitted": False}


async def test_check_in_faq_collision_selects_single_player_faq(
    db_session: AsyncSession,
) -> None:
    event = await create_event(db_session, "check-in-collision-event")
    await add_faq(
        db_session,
        faq_key="check_in_whole_team",
        category=FAQCategory.CHECK_IN,
        static_answer="Synthetic whole-team check-in answer.",
        event=event,
    )
    await add_faq(
        db_session,
        faq_key="check_in_one_player",
        category=FAQCategory.CHECK_IN,
        static_answer="Synthetic one-player check-in answer.",
        event=event,
    )
    message = interpreted(
        MessageIntent(
            type=IntentType.CHECK_IN,
            knowledge_topic=KnowledgeTopic.CHECK_IN_SINGLE_PLAYER,
            entities={"single_player": True},
        )
    )

    results = await SQLKnowledgeRetriever(Settings(active_event_id=event.id)).retrieve(
        db_session,
        KnowledgeQuery(interpreted_message=message),
    )

    assert results[0].faq_key == "check_in_one_player"
    assert results[0].value == "Synthetic one-player check-in answer."


async def test_missing_exact_topic_does_not_use_same_category_faq_or_green(
    db_session: AsyncSession,
) -> None:
    event = await create_event(db_session, "missing-topic-event")
    await add_faq(
        db_session,
        faq_key="fees_registration_fee",
        category=FAQCategory.FEES,
        static_answer="Synthetic registration fee answer.",
        event=event,
    )
    message = interpreted(MessageIntent(type=IntentType.EARLY_BIRD, category="U16"))

    results = await SQLKnowledgeRetriever(Settings(active_event_id=event.id)).retrieve(
        db_session,
        KnowledgeQuery(interpreted_message=message),
    )
    decision = DecisionEngine().decide(message, results_to_decision_context(results))

    assert results[0].found is False
    assert results[0].faq_key != "fees_registration_fee"
    assert decision.level != DecisionLevel.GREEN


async def test_multi_intent_missing_one_topic_prevents_green(
    db_session: AsyncSession,
) -> None:
    event = await create_event(db_session, "multi-missing-event")
    await add_rule(db_session, event, "U16", "category_playing_date", {"date": "2027-06-13"})
    await add_rule(db_session, event, "GENERAL", "maximum_players", {"maximum": 4})
    message = interpreted(
        MessageIntent(
            type=IntentType.SCHEDULE,
            category="U16",
            knowledge_topic=KnowledgeTopic.CATEGORY_PLAYING_DATE,
        ),
        MessageIntent(
            type=IntentType.TEAM_COMPOSITION,
            knowledge_topic=KnowledgeTopic.TEAM_MAX_PLAYERS,
            entities={"maximum_players": 4},
        ),
        MessageIntent(
            type=IntentType.ELIGIBILITY,
            knowledge_topic=KnowledgeTopic.FOREIGN_PLAYERS_ALLOWED,
            entities={"foreign_player": True},
        ),
    )

    results = await SQLKnowledgeRetriever(Settings(active_event_id=event.id)).retrieve(
        db_session,
        KnowledgeQuery(interpreted_message=message),
    )
    decision = DecisionEngine().decide(message, results_to_decision_context(results))

    assert [result.knowledge_topic for result in results] == [
        KnowledgeTopic.CATEGORY_PLAYING_DATE,
        KnowledgeTopic.TEAM_MAX_PLAYERS,
        KnowledgeTopic.FOREIGN_PLAYERS_ALLOWED,
    ]
    assert [result.found for result in results] == [True, True, False]
    assert decision.level != DecisionLevel.GREEN
