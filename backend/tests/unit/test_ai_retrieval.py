from datetime import UTC, date, datetime

from app.ai.retrieval import SQLKnowledgeRetriever, results_to_decision_context
from app.config.settings import Settings
from app.db.models.conversation import Conversation
from app.db.models.event import Event
from app.db.models.event_rule import EventRule
from app.policy.decision_engine import DecisionEngine
from app.schemas.enums import (
    ChannelName,
    DecisionLevel,
    EventStatus,
    IntentType,
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


async def test_green_fee_requires_active_event_rule(db_session: AsyncSession) -> None:
    event = await create_event(db_session, "fee-event")
    await add_rule(db_session, event, "U16", "registration_fee", {"amount_myr": 180})
    message = interpreted(MessageIntent(type=IntentType.FEE, category="U16"))

    results = await SQLKnowledgeRetriever(Settings(active_event_id=event.id)).retrieve(
        db_session,
        KnowledgeQuery(interpreted_message=message),
    )
    decision = DecisionEngine().decide(message, results_to_decision_context(results))

    assert results[0].found is True
    assert results[0].source_type == "event_rule"
    assert decision.level == DecisionLevel.GREEN


async def test_green_intent_without_active_event_is_not_green(db_session: AsyncSession) -> None:
    message = interpreted(MessageIntent(type=IntentType.FEE, category="U16"))

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
    message = interpreted(MessageIntent(type=IntentType.FEE, category="U16"))

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
        MessageIntent(type=IntentType.SCHEDULE, category="U16"),
        MessageIntent(type=IntentType.TEAM_COMPOSITION),
        MessageIntent(type=IntentType.ELIGIBILITY, entities={"foreign_player": True}),
    )

    results = await SQLKnowledgeRetriever(Settings(active_event_id=event.id)).retrieve(
        db_session,
        KnowledgeQuery(interpreted_message=message),
    )
    decision = DecisionEngine().decide(message, results_to_decision_context(results))

    assert [result.found for result in results] == [True, True, True]
    assert decision.level == DecisionLevel.GREEN
