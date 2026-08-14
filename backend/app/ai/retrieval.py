import json
from functools import lru_cache
from pathlib import Path
from typing import Protocol, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings, get_settings
from app.db.models.conversation import Conversation
from app.db.models.event import Event
from app.db.models.event_rule import EventRule
from app.db.models.faq_entry import FAQEntry
from app.schemas.decision import DecisionContext
from app.schemas.enums import (
    EventStatus,
    FAQStatus,
    IntentType,
    KnowledgeTopic,
    RuleStatus,
)
from app.schemas.faq import FAQMasterFile, FAQSeedEntry
from app.schemas.interpretation import MessageIntent
from app.schemas.retrieval import KnowledgeQuery, KnowledgeResult


class KnowledgeRetriever(Protocol):
    async def retrieve(self, session: AsyncSession, query: KnowledgeQuery) -> list[KnowledgeResult]:
        """Return typed trusted evidence for the interpreted participant request."""


class EmptyKnowledgeRetriever:
    async def retrieve(self, session: AsyncSession, query: KnowledgeQuery) -> list[KnowledgeResult]:
        return [
            KnowledgeResult(
                intent_type=intent.type,
                knowledge_topic=intent.knowledge_topic,
                found=False,
                confirmed=False,
                notes=["no retriever configured"],
            )
            for intent in query.interpreted_message.intents
        ]


class SQLKnowledgeRetriever:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def retrieve(self, session: AsyncSession, query: KnowledgeQuery) -> list[KnowledgeResult]:
        event = await self._resolve_event(session, query)
        results: list[KnowledgeResult] = []
        for intent in query.interpreted_message.intents:
            results.append(await self._retrieve_intent(session, intent, event))
        return results

    async def _resolve_event(
        self,
        session: AsyncSession,
        query: KnowledgeQuery,
    ) -> Event | None:
        if query.conversation_id is not None:
            conversation = await session.get(Conversation, query.conversation_id)
            if conversation is not None and conversation.event_id is not None:
                return await session.get(Event, conversation.event_id)

        if query.event_id is not None:
            return await session.get(Event, query.event_id)

        if self.settings.active_event_id is not None:
            return await session.get(Event, self.settings.active_event_id)

        return None

    async def _retrieve_intent(
        self,
        session: AsyncSession,
        intent: MessageIntent,
        event: Event | None,
    ) -> KnowledgeResult:
        canonical = canonical_intent(intent.type)
        if canonical in _lookup_intents():
            return await self._policy_result(session, intent, requires_lookup=True)
        if canonical in _human_intents():
            return await self._policy_result(session, intent, requires_human=True)
        if canonical == IntentType.UNKNOWN:
            return KnowledgeResult(
                intent_type=intent.type,
                knowledge_topic=intent.knowledge_topic,
                found=False,
                confirmed=False,
                requires_human=True,
                notes=["unknown request has no approved knowledge source"],
            )

        topic = knowledge_topic_for_intent(intent)
        if topic is None:
            return _missing_topic_result(intent)

        faq_key = _faq_key_for_topic(topic)
        faq_result = await self._faq_entry_result(
            session,
            intent,
            topic,
            faq_key,
            event,
            event_specific=True,
        )
        if faq_result is not None:
            return faq_result

        global_faq_result = await self._faq_entry_result(
            session,
            intent,
            topic,
            faq_key,
            event,
            event_specific=False,
        )
        if global_faq_result is not None:
            return global_faq_result

        structured_result = await self._structured_event_result(session, intent, topic, event)
        if structured_result is not None:
            return structured_result

        return self._faq_master_fallback(intent, topic)

    async def _policy_result(
        self,
        session: AsyncSession,
        intent: MessageIntent,
        *,
        requires_lookup: bool = False,
        requires_human: bool = False,
    ) -> KnowledgeResult:
        faq = await self._first_faq_by_key(session, intent)
        return KnowledgeResult(
            intent_type=intent.type,
            knowledge_topic=intent.knowledge_topic,
            found=True,
            source_type="faq_entry" if faq is not None else "faq_master",
            source_identifier=(
                faq.faq_key if faq is not None else canonical_intent(intent.type).value
            ),
            event_id=faq.event_id if faq is not None else None,
            faq_key=faq.faq_key if faq is not None else None,
            value=faq.static_answer if faq is not None else None,
            confirmed=True,
            requires_lookup=requires_lookup,
            requires_human=requires_human,
            last_updated_at=faq.last_updated_at if faq is not None else None,
        )

    async def _structured_event_result(
        self,
        session: AsyncSession,
        intent: MessageIntent,
        topic: KnowledgeTopic,
        event: Event | None,
    ) -> KnowledgeResult | None:
        if event is None:
            return _missing_event_result(intent, topic)
        event_confirmed = _event_is_confirmed(event)

        event_value = _event_value_for_topic(event, topic)
        if event_value is not None:
            return KnowledgeResult(
                intent_type=intent.type,
                knowledge_topic=topic,
                found=True,
                source_type="event",
                source_identifier=f"{event.id}:{topic.value}",
                event_id=event.id,
                value=event_value,
                confirmed=event_confirmed,
            )

        rule_types = _rule_types_for_topic(topic)
        if not rule_types:
            return None

        rule = await self._find_event_rule(session, event.id, intent.category, rule_types)
        if rule is None:
            return None

        return KnowledgeResult(
            intent_type=intent.type,
            knowledge_topic=topic,
            found=True,
            source_type="event_rule",
            source_identifier=str(rule.id),
            event_id=event.id,
            rule_type=rule.rule_type,
            value=rule.value,
            confirmed=event_confirmed,
            last_updated_at=rule.updated_at,
        )

    async def _faq_entry_result(
        self,
        session: AsyncSession,
        intent: MessageIntent,
        topic: KnowledgeTopic,
        faq_key: str,
        event: Event | None,
        *,
        event_specific: bool,
    ) -> KnowledgeResult | None:
        conditions = [
            FAQEntry.faq_key == faq_key,
            FAQEntry.status == FAQStatus.APPROVED,
        ]
        if event_specific:
            if event is None:
                return None
            conditions.append(FAQEntry.event_id == event.id)
        else:
            conditions.append(FAQEntry.event_id.is_(None))

        faq = await session.scalar(
            select(FAQEntry)
            .where(*conditions)
            .order_by(FAQEntry.created_at.desc(), FAQEntry.faq_key.asc())
            .limit(1)
        )
        if faq is None:
            return None

        found = bool(faq.static_answer) or faq.requires_lookup or faq.requires_human
        if not found:
            return None
        event_confirmed = True
        if event_specific:
            event_confirmed = event is not None and _event_is_confirmed(event)
        return KnowledgeResult(
            intent_type=intent.type,
            knowledge_topic=topic,
            found=found,
            source_type="faq_entry",
            source_identifier=faq.faq_key,
            event_id=faq.event_id,
            faq_key=faq.faq_key,
            value=faq.static_answer,
            confirmed=(
                found
                and event_confirmed
                and faq.auto_reply_allowed
                and not faq.requires_lookup
                and not faq.requires_human
            ),
            requires_lookup=faq.requires_lookup,
            requires_human=faq.requires_human,
            last_updated_at=faq.last_updated_at,
        )

    async def _first_faq_by_key(
        self,
        session: AsyncSession,
        intent: MessageIntent,
    ) -> FAQEntry | None:
        prefixes = _faq_key_prefixes(canonical_intent(intent.type))
        if not prefixes:
            return None
        return cast(
            FAQEntry | None,
            await session.scalar(
                select(FAQEntry)
                .where(
                    FAQEntry.status == FAQStatus.APPROVED,
                    FAQEntry.faq_key.in_(prefixes),
                )
                .order_by(FAQEntry.created_at.desc())
                .limit(1)
            ),
        )

    async def _find_event_rule(
        self,
        session: AsyncSession,
        event_id: UUID,
        category: str | None,
        rule_types: list[str],
    ) -> EventRule | None:
        categories = [category.upper()] if category else []
        categories.extend(["GENERAL", "ALL"])
        for rule_type in rule_types:
            for category_candidate in categories:
                rule = await session.scalar(
                    select(EventRule)
                    .where(
                        EventRule.event_id == event_id,
                        EventRule.status == RuleStatus.ACTIVE,
                        EventRule.rule_type == rule_type,
                        EventRule.category == category_candidate,
                    )
                    .order_by(EventRule.updated_at.desc(), EventRule.id.desc())
                    .limit(1)
                )
                if rule is not None:
                    return rule
        return None

    def _faq_master_fallback(
        self,
        intent: MessageIntent,
        topic: KnowledgeTopic,
    ) -> KnowledgeResult:
        entry = _faq_master_entry(topic)
        if entry is None:
            return KnowledgeResult(
                intent_type=intent.type,
                knowledge_topic=topic,
                found=False,
                confirmed=False,
                notes=["no exact approved FAQ master entry exists for the knowledge topic"],
            )
        found = bool(entry.static_answer) or entry.requires_lookup or entry.requires_human
        return KnowledgeResult(
            intent_type=intent.type,
            knowledge_topic=topic,
            found=found,
            source_type="faq_master",
            source_identifier=entry.faq_key,
            faq_key=entry.faq_key,
            value=entry.static_answer,
            confirmed=bool(entry.static_answer) and entry.auto_reply_allowed,
            requires_lookup=entry.requires_lookup,
            requires_human=entry.requires_human,
            notes=[entry.notes] if entry.notes else [],
        )


def results_to_decision_context(results: list[KnowledgeResult]) -> DecisionContext:
    return DecisionContext(
        evidence=[result.to_evidence() for result in results],
        requires_human_authority=any(result.requires_human for result in results),
    )


def canonical_intent(intent_type: IntentType) -> IntentType:
    aliases = {
        IntentType.REGISTRATION: IntentType.REGISTRATION_INFO,
        IntentType.REGISTRATION_EXCEPTION: IntentType.LATE_REGISTRATION,
        IntentType.FEES: IntentType.FEE,
        IntentType.EARLY_BIRD: IntentType.FEE,
        IntentType.PLAYER_RESTRICTIONS: IntentType.ELIGIBILITY,
        IntentType.PAYMENT_VERIFICATION: IntentType.PAYMENT_STATUS,
        IntentType.REFUND_REQUEST: IntentType.REFUND,
        IntentType.MERCHANDISE_ORDER_LOOKUP: IntentType.MERCHANDISE_ORDER,
        IntentType.TECHNICAL_REGISTRATION_FAILURE: IntentType.TECHNICAL_REGISTRATION,
        IntentType.GENERAL: IntentType.UNKNOWN,
    }
    return aliases.get(intent_type, intent_type)


def _lookup_intents() -> set[IntentType]:
    return {
        IntentType.REGISTRATION_STATUS,
        IntentType.PAYMENT_STATUS,
        IntentType.MERCHANDISE_ORDER,
        IntentType.TECHNICAL_REGISTRATION,
    }


def _human_intents() -> set[IntentType]:
    return {
        IntentType.LATE_REGISTRATION,
        IntentType.ELIGIBILITY_EXCEPTION,
        IntentType.SCHEDULE_EXCEPTION,
        IntentType.RULE_DISPUTE,
        IntentType.REFUND,
        IntentType.OVERPAYMENT,
        IntentType.WITHDRAWAL,
        IntentType.WALKOVER_DISPUTE,
        IntentType.COMMERCIAL,
        IntentType.HUMAN_REQUEST,
    }


TOPIC_FAQ_KEYS: dict[KnowledgeTopic, str] = {
    KnowledgeTopic.REGISTRATION_METHOD: "registration_how_to_register",
    KnowledgeTopic.REGISTRATION_OPEN: "registration_is_open",
    KnowledgeTopic.REGISTRATION_DEADLINE: "registration_deadline",
    KnowledgeTopic.REGISTRATION_CLOSE_TIME: "registration_close_time",
    KnowledgeTopic.REGISTRATION_LINK: "registration_link_or_qr",
    KnowledgeTopic.REGISTRATION_FEE: "fees_registration_fee",
    KnowledgeTopic.CATEGORY_FEE: "fees_different_by_category",
    KnowledgeTopic.EARLY_BIRD_FEE: "fees_early_bird",
    KnowledgeTopic.EARLY_BIRD_DEADLINE: "fees_early_bird_end",
    KnowledgeTopic.TEAM_MIN_PLAYERS: "team_min_players",
    KnowledgeTopic.TEAM_MAX_PLAYERS: "team_max_players",
    KnowledgeTopic.TEAM_THREE_PLAYERS: "team_three_players",
    KnowledgeTopic.TEAM_MIXED_GENDER: "team_mixed_gender",
    KnowledgeTopic.ELIGIBILITY_CATEGORY: "eligibility_category",
    KnowledgeTopic.ELIGIBILITY_AGE_METHOD: "eligibility_birth_year_or_birthday",
    KnowledgeTopic.ELIGIBILITY_PLAY_UP: "eligibility_younger_play_older",
    KnowledgeTopic.FOREIGN_PLAYERS_ALLOWED: "eligibility_foreign_players",
    KnowledgeTopic.FOREIGN_PLAYER_MAX: "eligibility_foreign_player_count",
    KnowledgeTopic.NATIONAL_PLAYER_POLICY: "eligibility_national_players",
    KnowledgeTopic.CATEGORY_PLAYING_DATE: "schedule_category_date",
    KnowledgeTopic.CATEGORIES_SAME_DAY: "schedule_two_categories_same_day",
    KnowledgeTopic.KEEP_BOTH_EVENT_DAYS: "schedule_keep_both_days",
    KnowledgeTopic.SCHEDULE_RELEASE: "schedule_final_release",
    KnowledgeTopic.RULES_LINK: "rules_location",
    KnowledgeTopic.CHECK_IN_WHOLE_TEAM: "check_in_whole_team",
    KnowledgeTopic.CHECK_IN_SINGLE_PLAYER: "check_in_one_player",
    KnowledgeTopic.MERCHANDISE_INCLUDED: "merchandise_included",
    KnowledgeTopic.MERCHANDISE_PRICE: "merchandise_price",
    KnowledgeTopic.MERCHANDISE_ORDER_LINK: "merchandise_order_where",
    KnowledgeTopic.MERCHANDISE_PREORDER_DEADLINE: "merchandise_preorder_deadline",
    KnowledgeTopic.MERCHANDISE_DELIVERY_FEE: "merchandise_delivery_fee",
}


TOPIC_RULE_TYPES: dict[KnowledgeTopic, list[str]] = {
    KnowledgeTopic.REGISTRATION_FEE: ["registration_fee", "category_fee", "fee"],
    KnowledgeTopic.CATEGORY_FEE: ["category_fee", "registration_fee", "fee"],
    KnowledgeTopic.EARLY_BIRD_FEE: ["early_bird_fee"],
    KnowledgeTopic.EARLY_BIRD_DEADLINE: ["early_bird_deadline", "early_bird_period"],
    KnowledgeTopic.TEAM_MIN_PLAYERS: ["minimum_players", "player_count"],
    KnowledgeTopic.TEAM_MAX_PLAYERS: ["maximum_players", "player_count"],
    KnowledgeTopic.TEAM_THREE_PLAYERS: ["minimum_players", "player_count"],
    KnowledgeTopic.TEAM_MIXED_GENDER: ["mixed_gender_policy", "gender_policy"],
    KnowledgeTopic.ELIGIBILITY_CATEGORY: ["minimum_birth_year", "eligibility"],
    KnowledgeTopic.ELIGIBILITY_AGE_METHOD: ["eligibility_age_method", "eligibility"],
    KnowledgeTopic.ELIGIBILITY_PLAY_UP: ["play_up_policy", "eligibility"],
    KnowledgeTopic.FOREIGN_PLAYERS_ALLOWED: [
        "foreign_players_allowed",
        "foreign_player_policy",
    ],
    KnowledgeTopic.FOREIGN_PLAYER_MAX: [
        "foreign_player_max",
        "maximum_foreign_players",
        "foreign_player_policy",
    ],
    KnowledgeTopic.NATIONAL_PLAYER_POLICY: [
        "national_player_policy",
        "national_youth_player_policy",
        "player_restrictions",
    ],
    KnowledgeTopic.CATEGORY_PLAYING_DATE: ["category_playing_date", "playing_date", "schedule"],
    KnowledgeTopic.CATEGORIES_SAME_DAY: ["categories_same_day", "schedule"],
    KnowledgeTopic.KEEP_BOTH_EVENT_DAYS: ["keep_both_event_days", "schedule"],
    KnowledgeTopic.SCHEDULE_RELEASE: ["schedule_release", "schedule"],
    KnowledgeTopic.RULES_LINK: ["rules_link", "rules_url", "rules"],
    KnowledgeTopic.CHECK_IN_WHOLE_TEAM: ["check_in_whole_team", "check_in"],
    KnowledgeTopic.CHECK_IN_SINGLE_PLAYER: ["check_in_single_player", "check_in"],
    KnowledgeTopic.MERCHANDISE_INCLUDED: ["merchandise_included", "merchandise"],
    KnowledgeTopic.MERCHANDISE_PRICE: ["merchandise_price", "merchandise"],
    KnowledgeTopic.MERCHANDISE_ORDER_LINK: ["merchandise_order_link", "merchandise"],
    KnowledgeTopic.MERCHANDISE_PREORDER_DEADLINE: [
        "merchandise_preorder_deadline",
        "merchandise_deadline",
    ],
    KnowledgeTopic.MERCHANDISE_DELIVERY_FEE: [
        "merchandise_delivery_fee",
        "merchandise_delivery",
    ],
}


def knowledge_topic_for_intent(intent: MessageIntent) -> KnowledgeTopic | None:
    if intent.knowledge_topic is not None:
        return intent.knowledge_topic

    if intent.type in {IntentType.FEE, IntentType.FEES}:
        if intent.entities.get("registration_fee") is True:
            return KnowledgeTopic.REGISTRATION_FEE
        if intent.entities.get("category_fee") is True:
            return KnowledgeTopic.CATEGORY_FEE
        if intent.entities.get("early_bird_fee") is True:
            return KnowledgeTopic.EARLY_BIRD_FEE
        if intent.entities.get("early_bird_deadline") is True:
            return KnowledgeTopic.EARLY_BIRD_DEADLINE
    if intent.type == IntentType.EARLY_BIRD:
        if intent.entities.get("early_bird_fee") is True:
            return KnowledgeTopic.EARLY_BIRD_FEE
        if intent.entities.get("early_bird_deadline") is True:
            return KnowledgeTopic.EARLY_BIRD_DEADLINE
    if intent.type == IntentType.ELIGIBILITY and intent.entities.get("foreign_player") is True:
        return KnowledgeTopic.FOREIGN_PLAYERS_ALLOWED
    if intent.type == IntentType.ELIGIBILITY and (
        intent.category or "birth_year" in intent.entities
    ):
        return KnowledgeTopic.ELIGIBILITY_CATEGORY
    if intent.type == IntentType.SCHEDULE and intent.category:
        return KnowledgeTopic.CATEGORY_PLAYING_DATE
    if intent.type == IntentType.RULES:
        return KnowledgeTopic.RULES_LINK
    if intent.type == IntentType.TEAM_COMPOSITION:
        if intent.entities.get("requested_players") == 3:
            return KnowledgeTopic.TEAM_THREE_PLAYERS
        if "minimum_players" in intent.entities:
            return KnowledgeTopic.TEAM_MIN_PLAYERS
        if "maximum_players" in intent.entities:
            return KnowledgeTopic.TEAM_MAX_PLAYERS

    if intent.type == IntentType.PLAYER_RESTRICTIONS:
        if intent.entities.get("national_player") is True:
            return KnowledgeTopic.NATIONAL_PLAYER_POLICY
        if intent.entities.get("foreign_player_count") is True:
            return KnowledgeTopic.FOREIGN_PLAYER_MAX
        if intent.entities.get("foreign_player") is True:
            return KnowledgeTopic.FOREIGN_PLAYERS_ALLOWED

    if intent.type == IntentType.CHECK_IN:
        if intent.entities.get("single_player") is True:
            return KnowledgeTopic.CHECK_IN_SINGLE_PLAYER
        if intent.entities.get("whole_team") is True:
            return KnowledgeTopic.CHECK_IN_WHOLE_TEAM

    return None


def _faq_key_for_topic(topic: KnowledgeTopic) -> str:
    return TOPIC_FAQ_KEYS[topic]


def _rule_types_for_topic(topic: KnowledgeTopic) -> list[str]:
    return TOPIC_RULE_TYPES.get(topic, [])


def _faq_key_prefixes(intent_type: IntentType) -> list[str]:
    mapping = {
        IntentType.REGISTRATION_STATUS: [
            "registration_status_lookup",
            "payment_registration_confirmed",
        ],
        IntentType.LATE_REGISTRATION: ["registration_after_deadline"],
        IntentType.PAYMENT_STATUS: ["payment_received", "payment_confirmation"],
        IntentType.REFUND: ["payment_refund"],
        IntentType.OVERPAYMENT: ["payment_wrong_amount"],
        IntentType.MERCHANDISE_ORDER: ["merchandise_arrival", "merchandise_delivery_address"],
        IntentType.TECHNICAL_REGISTRATION: [
            "technical_form_not_working",
            "technical_upload_problem",
        ],
        IntentType.COMMERCIAL: ["commercial_booth_rental"],
    }
    return mapping.get(intent_type, [])


def _event_is_confirmed(event: Event) -> bool:
    return event.status == EventStatus.PUBLISHED and event.is_active


def _event_value_for_topic(event: Event, topic: KnowledgeTopic) -> dict[str, object] | None:
    if topic == KnowledgeTopic.REGISTRATION_METHOD and event.registration_url:
        return {"registration_url": event.registration_url}
    if topic == KnowledgeTopic.REGISTRATION_LINK and event.registration_url:
        return {"registration_url": event.registration_url}
    if topic == KnowledgeTopic.REGISTRATION_OPEN:
        return {
            "registration_open": event.registration_open,
            "registration_deadline": (
                event.registration_deadline.isoformat()
                if event.registration_deadline is not None
                else None
            ),
        }
    if topic in {
        KnowledgeTopic.REGISTRATION_DEADLINE,
        KnowledgeTopic.REGISTRATION_CLOSE_TIME,
    } and event.registration_deadline is not None:
        return {"registration_deadline": event.registration_deadline.isoformat()}
    if topic == KnowledgeTopic.KEEP_BOTH_EVENT_DAYS and (
        event.start_date is not None or event.end_date is not None
    ):
        return {
            "start_date": event.start_date.isoformat() if event.start_date else None,
            "end_date": event.end_date.isoformat() if event.end_date else None,
        }
    return None


def _missing_topic_result(intent: MessageIntent) -> KnowledgeResult:
    return KnowledgeResult(
        intent_type=intent.type,
        found=False,
        confirmed=False,
        notes=["no exact knowledge topic was supplied or safely inferred"],
    )


def _missing_event_result(intent: MessageIntent, topic: KnowledgeTopic) -> KnowledgeResult:
    return KnowledgeResult(
        intent_type=intent.type,
        knowledge_topic=topic,
        found=False,
        confirmed=False,
        notes=["no active or conversation event is available"],
    )


@lru_cache
def _faq_master() -> FAQMasterFile:
    path = Path("knowledge/faq_master.json")
    return FAQMasterFile.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _faq_master_entry(topic: KnowledgeTopic) -> FAQSeedEntry | None:
    faq_key = _faq_key_for_topic(topic)
    entries = _faq_master().entries
    for entry in entries:
        if entry.faq_key == faq_key:
            return entry
    return None
