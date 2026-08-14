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
    AnswerSource,
    EventStatus,
    FAQCategory,
    FAQStatus,
    IntentType,
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
                found=False,
                confirmed=False,
                requires_human=True,
                notes=["unknown request has no approved knowledge source"],
            )

        structured_result = await self._structured_event_result(session, intent, event)
        if structured_result is not None:
            return structured_result

        faq_result = await self._faq_entry_result(session, intent, event, event_specific=True)
        if faq_result is not None:
            return faq_result

        global_faq_result = await self._faq_entry_result(
            session,
            intent,
            event,
            event_specific=False,
        )
        if global_faq_result is not None:
            return global_faq_result

        return self._faq_master_fallback(intent)

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
        event: Event | None,
    ) -> KnowledgeResult | None:
        canonical = canonical_intent(intent.type)
        if event is None:
            return _missing_event_result(intent)
        event_confirmed = _event_is_confirmed(event)

        if canonical == IntentType.REGISTRATION_INFO:
            return KnowledgeResult(
                intent_type=intent.type,
                found=bool(event.registration_url or event.registration_deadline),
                source_type="event",
                source_identifier=str(event.id),
                event_id=event.id,
                value={
                    "registration_open": event.registration_open,
                    "registration_deadline": (
                        event.registration_deadline.isoformat()
                        if event.registration_deadline is not None
                        else None
                    ),
                    "registration_url": event.registration_url,
                },
                confirmed=event_confirmed
                and bool(event.registration_url or event.registration_deadline),
            )

        if canonical == IntentType.SCHEDULE and not intent.category:
            return KnowledgeResult(
                intent_type=intent.type,
                found=bool(event.start_date or event.end_date),
                source_type="event",
                source_identifier=str(event.id),
                event_id=event.id,
                value={
                    "start_date": event.start_date.isoformat() if event.start_date else None,
                    "end_date": event.end_date.isoformat() if event.end_date else None,
                    "venue": event.venue,
                },
                confirmed=event_confirmed and bool(event.start_date or event.end_date),
            )

        rule_types = _rule_types_for_intent(canonical, intent)
        if not rule_types:
            return None

        rule = await self._find_event_rule(session, event.id, intent.category, rule_types)
        if rule is None:
            return None

        return KnowledgeResult(
            intent_type=intent.type,
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
        event: Event | None,
        *,
        event_specific: bool,
    ) -> KnowledgeResult | None:
        category = _faq_category_for_intent(canonical_intent(intent.type))
        if category is None:
            return None
        conditions = [
            FAQEntry.category == category,
            FAQEntry.status == FAQStatus.APPROVED,
        ]
        if event_specific:
            if event is None:
                return None
            conditions.append(FAQEntry.event_id == event.id)
        else:
            conditions.append(FAQEntry.event_id.is_(None))

        faq = await session.scalar(
            select(FAQEntry).where(*conditions).order_by(FAQEntry.created_at.desc()).limit(1)
        )
        if faq is None:
            return None

        found = bool(faq.static_answer) or faq.requires_lookup or faq.requires_human
        return KnowledgeResult(
            intent_type=intent.type,
            found=found,
            source_type="faq_entry",
            source_identifier=faq.faq_key,
            event_id=faq.event_id,
            faq_key=faq.faq_key,
            value=faq.static_answer,
            confirmed=found and not faq.requires_lookup and not faq.requires_human,
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
        rules = list(
            await session.scalars(
                select(EventRule)
                .where(
                    EventRule.event_id == event_id,
                    EventRule.status == RuleStatus.ACTIVE,
                    EventRule.rule_type.in_(rule_types),
                    EventRule.category.in_(categories),
                )
                .limit(20)
            )
        )
        if not rules:
            return None
        if category:
            exact = category.upper()
            for rule in rules:
                if rule.category.upper() == exact:
                    return rule
        return rules[0]

    def _faq_master_fallback(self, intent: MessageIntent) -> KnowledgeResult:
        entry = _faq_master_entry(canonical_intent(intent.type))
        if entry is None:
            return KnowledgeResult(intent_type=intent.type, found=False, confirmed=False)
        found = bool(entry.static_answer) or entry.requires_lookup or entry.requires_human
        return KnowledgeResult(
            intent_type=intent.type,
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


def _rule_types_for_intent(intent_type: IntentType, intent: MessageIntent) -> list[str]:
    if intent_type == IntentType.FEE:
        return ["registration_fee", "category_fee", "fee"]
    if intent_type == IntentType.TEAM_COMPOSITION:
        return ["player_count", "maximum_players", "minimum_players"]
    if intent_type == IntentType.ELIGIBILITY and intent.entities.get("foreign_player") is True:
        return ["foreign_player_policy"]
    if intent_type == IntentType.ELIGIBILITY:
        return ["minimum_birth_year", "eligibility"]
    if intent_type == IntentType.SCHEDULE:
        return ["category_playing_date", "playing_date", "schedule"]
    if intent_type == IntentType.RULES:
        return ["rules_url", "rules"]
    if intent_type == IntentType.CHECK_IN:
        return ["check_in"]
    if intent_type == IntentType.MERCHANDISE_INFO:
        return ["merchandise", "merchandise_price"]
    return []


def _faq_category_for_intent(intent_type: IntentType) -> FAQCategory | None:
    mapping = {
        IntentType.REGISTRATION_INFO: FAQCategory.REGISTRATION,
        IntentType.REGISTRATION_STATUS: FAQCategory.REGISTRATION,
        IntentType.LATE_REGISTRATION: FAQCategory.REGISTRATION,
        IntentType.FEE: FAQCategory.FEES,
        IntentType.TEAM_COMPOSITION: FAQCategory.TEAM_COMPOSITION,
        IntentType.ELIGIBILITY: FAQCategory.ELIGIBILITY,
        IntentType.ELIGIBILITY_EXCEPTION: FAQCategory.ELIGIBILITY,
        IntentType.SCHEDULE: FAQCategory.SCHEDULE,
        IntentType.SCHEDULE_EXCEPTION: FAQCategory.SCHEDULE,
        IntentType.RULES: FAQCategory.RULES,
        IntentType.RULE_DISPUTE: FAQCategory.RULES,
        IntentType.CHECK_IN: FAQCategory.CHECK_IN,
        IntentType.PAYMENT_STATUS: FAQCategory.PAYMENT,
        IntentType.REFUND: FAQCategory.PAYMENT,
        IntentType.OVERPAYMENT: FAQCategory.PAYMENT,
        IntentType.WITHDRAWAL: FAQCategory.WITHDRAWAL,
        IntentType.WALKOVER_DISPUTE: FAQCategory.WITHDRAWAL,
        IntentType.MERCHANDISE_INFO: FAQCategory.MERCHANDISE,
        IntentType.MERCHANDISE_ORDER: FAQCategory.MERCHANDISE,
        IntentType.TECHNICAL_REGISTRATION: FAQCategory.TECHNICAL,
        IntentType.COMMERCIAL: FAQCategory.COMMERCIAL,
    }
    return mapping.get(intent_type)


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


def _missing_event_result(intent: MessageIntent) -> KnowledgeResult:
    return KnowledgeResult(
        intent_type=intent.type,
        found=False,
        confirmed=False,
        notes=["no active or conversation event is available"],
    )


@lru_cache
def _faq_master() -> FAQMasterFile:
    path = Path("knowledge/faq_master.json")
    return FAQMasterFile.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _faq_master_entry(intent_type: IntentType) -> FAQSeedEntry | None:
    prefixes = _faq_key_prefixes(intent_type)
    entries = _faq_master().entries
    if prefixes:
        for entry in entries:
            if entry.faq_key in prefixes:
                return entry
    category = _faq_category_for_intent(intent_type)
    if category is None:
        return None
    for entry in entries:
        if entry.category == category:
            if entry.answer_source not in {AnswerSource.EVENT_CONFIG, AnswerSource.RULE_ENGINE}:
                return entry
            if entry.static_answer is not None:
                return entry
    return None
