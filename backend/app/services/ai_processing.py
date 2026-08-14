from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import (
    AIProvider,
    AIProviderCallMetadata,
    AIProviderError,
    ResponseGenerationRequest,
)
from app.ai.context import ConversationContextBuilder
from app.ai.responder import ResponseGenerator
from app.ai.retrieval import KnowledgeRetriever, SQLKnowledgeRetriever, results_to_decision_context
from app.config.settings import Settings, get_settings
from app.db.models.ai_processing_run import AIProcessingRun
from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.policy.decision_engine import DecisionEngine
from app.schemas.decision import DecisionResult
from app.schemas.enums import AIProcessingStatus, ContentType, MessageDirection, SenderType
from app.schemas.interpretation import InterpretationRequest, InterpretedMessage
from app.schemas.retrieval import KnowledgeQuery, KnowledgeResult


class AIProcessingService:
    def __init__(
        self,
        provider: AIProvider,
        settings: Settings | None = None,
        retriever: KnowledgeRetriever | None = None,
        context_builder: ConversationContextBuilder | None = None,
        decision_engine: DecisionEngine | None = None,
        response_generator: ResponseGenerator | None = None,
    ) -> None:
        self.provider = provider
        self.settings = settings or get_settings()
        self.retriever = retriever or SQLKnowledgeRetriever(self.settings)
        self.context_builder = context_builder or ConversationContextBuilder(self.settings)
        self.decision_engine = decision_engine or DecisionEngine()
        self.response_generator = response_generator or ResponseGenerator(provider)

    async def process_message(
        self,
        session: AsyncSession,
        message_id: UUID,
        *,
        dry_run: bool = False,
    ) -> AIProcessingRun:
        message = await session.get(Message, message_id)
        if message is None:
            raise ValueError("message_id was not found")

        conversation = await session.get(Conversation, message.conversation_id)
        if conversation is None:
            raise ValueError("message conversation was not found")

        run = self._new_run(message, conversation)
        if not dry_run:
            session.add(run)
            await session.flush()

        if not self.settings.ai_processing_enabled:
            run.processing_status = AIProcessingStatus.SKIPPED
            run.error_code = "AI_PROCESSING_DISABLED"
            run.error_message = "AI processing is disabled by configuration"
            run.completed_at = _utcnow()
            if not dry_run:
                await session.commit()
            return run

        if (
            _enum_value(message.direction) != MessageDirection.INBOUND.value
            or _enum_value(message.sender_type) != SenderType.PARTICIPANT.value
        ):
            run.processing_status = AIProcessingStatus.SKIPPED
            run.error_code = "NOT_INBOUND_PARTICIPANT_MESSAGE"
            run.error_message = "Only inbound participant messages are eligible for AI processing"
            run.completed_at = _utcnow()
            if not dry_run:
                await session.commit()
            return run

        if _enum_value(message.content_type) != ContentType.TEXT.value or not message.text_content:
            run.processing_status = AIProcessingStatus.SKIPPED
            run.error_code = "UNSUPPORTED_MESSAGE"
            run.error_message = "Only text messages are supported for Phase 2 AI processing"
            run.completed_at = _utcnow()
            if not dry_run:
                await session.commit()
            return run

        try:
            context = await self.context_builder.build(session, conversation.id)
            event_id = conversation.event_id or self.settings.active_event_id
            interpreted = await self.provider.interpret_message(
                InterpretationRequest(
                    message_text=message.text_content,
                    channel=_enum_value(conversation.channel),
                    event_id=str(event_id) if event_id else None,
                    conversation_id=str(conversation.id),
                    recent_messages=context.messages,
                )
            )
            knowledge_results = await self.retriever.retrieve(
                session,
                KnowledgeQuery(
                    interpreted_message=interpreted,
                    conversation_id=conversation.id,
                    event_id=event_id,
                ),
            )
            decision = self.decision_engine.decide(
                interpreted,
                results_to_decision_context(knowledge_results),
            )
            generated = await self.response_generator.generate(
                request=_response_generator_request(
                    message_text=message.text_content,
                    interpreted=interpreted,
                    knowledge_results=knowledge_results,
                    context_lines=context.as_lines(),
                    decision=decision,
                ),
            )

            if decision.auto_reply_allowed and not generated.text:
                raise ValueError("GREEN draft response cannot be empty")

            run.primary_language = interpreted.primary_language
            run.language_mode = interpreted.language_mode
            run.interpreted_intents = [
                intent.model_dump(mode="json") for intent in interpreted.intents
            ]
            run.decision_level = decision.level
            run.decision_reason = (
                decision.reason_code.value
                if decision.reason_code is not None
                else (decision.notes[0] if decision.notes else None)
            )
            run.knowledge_found = any(result.found for result in knowledge_results)
            run.knowledge_source = _knowledge_source_summary(knowledge_results)
            run.requires_clarification = bool(
                interpreted.requires_clarification or decision.clarification_fields
            )
            run.recommended_pic_role = decision.assigned_pic_role
            run.draft_response = generated.text
            run.processing_status = AIProcessingStatus.COMPLETED
            run.completed_at = _utcnow()
            _apply_metadata(
                run,
                self.provider.interpretation_metadata,
                self.provider.response_metadata,
            )
        except (AIProviderError, ValueError) as exc:
            run.processing_status = AIProcessingStatus.FAILED
            run.error_code = type(exc).__name__
            run.error_message = _safe_error_message(exc)
            run.completed_at = _utcnow()

        if not dry_run:
            await session.commit()
        return run

    def _new_run(self, message: Message, conversation: Conversation) -> AIProcessingRun:
        return AIProcessingRun(
            id=uuid4(),
            message_id=message.id,
            conversation_id=conversation.id,
            event_id=conversation.event_id or self.settings.active_event_id,
            provider=_provider_name(self.provider),
            model=_provider_model(self.provider),
            interpreted_intents=[],
            processing_status=AIProcessingStatus.PENDING,
            knowledge_found=False,
            requires_clarification=False,
        )


def _provider_name(provider: AIProvider) -> str:
    value = getattr(provider, "provider_name", None)
    return value if isinstance(value, str) else provider.__class__.__name__


def _provider_model(provider: AIProvider) -> str | None:
    value = getattr(provider, "model", None)
    return value if isinstance(value, str) else None


def _enum_value(value: object) -> str:
    raw = getattr(value, "value", value)
    return raw if isinstance(raw, str) else str(raw)


def _response_generator_request(
    *,
    message_text: str,
    interpreted: InterpretedMessage,
    knowledge_results: list[KnowledgeResult],
    context_lines: list[str],
    decision: DecisionResult,
) -> ResponseGenerationRequest:
    return ResponseGenerationRequest(
        interpreted_message=interpreted,
        decision_result=decision,
        knowledge_results=knowledge_results,
        conversation_context=context_lines,
        response_language=interpreted.primary_language.value,
        participant_text=message_text,
    )


def _knowledge_source_summary(results: list[KnowledgeResult]) -> str | None:
    labels = [result.source_label for result in results if result.source_label]
    if not labels:
        return None
    return ", ".join(labels)[:240]


def _apply_metadata(
    run: AIProcessingRun,
    interpretation: AIProviderCallMetadata | None,
    response: AIProviderCallMetadata | None,
) -> None:
    request_ids = [
        item.provider_request_id
        for item in [interpretation, response]
        if item is not None and item.provider_request_id
    ]
    run.provider_request_id = ",".join(request_ids)[:160] if request_ids else None
    run.input_tokens = _sum_optional(
        interpretation.input_tokens if interpretation else None,
        response.input_tokens if response else None,
    )
    run.output_tokens = _sum_optional(
        interpretation.output_tokens if interpretation else None,
        response.output_tokens if response else None,
    )
    run.total_tokens = _sum_optional(
        interpretation.total_tokens if interpretation else None,
        response.total_tokens if response else None,
    )


def _sum_optional(left: int | None, right: int | None) -> int | None:
    values = [value for value in [left, right] if value is not None]
    if not values:
        return None
    return sum(values)


def _safe_error_message(exc: Exception) -> str:
    return str(exc).replace("\n", " ")[:500]


def _utcnow() -> datetime:
    return datetime.now(UTC)
