from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings, get_settings
from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.messaging.base import IncomingMessage
from app.messaging.whatsapp import WhatsAppStatusNotification
from app.schemas.enums import (
    AuditActorType,
    ChannelName,
    ContentType,
    ConversationState,
    MessageDeliveryStatus,
    MessageDirection,
    SenderType,
)
from app.services.audit import record_audit_event

SUCCESS_STATUS_ORDER: dict[MessageDeliveryStatus, int] = {
    MessageDeliveryStatus.PENDING: 0,
    MessageDeliveryStatus.ACCEPTED: 1,
    MessageDeliveryStatus.SENT: 2,
    MessageDeliveryStatus.DELIVERED: 3,
    MessageDeliveryStatus.READ: 4,
}

META_STATUS_MAP: dict[str, MessageDeliveryStatus] = {
    "accepted": MessageDeliveryStatus.ACCEPTED,
    "sent": MessageDeliveryStatus.SENT,
    "delivered": MessageDeliveryStatus.DELIVERED,
    "read": MessageDeliveryStatus.READ,
    "failed": MessageDeliveryStatus.FAILED,
}


class WhatsAppWebhookProcessingResult(BaseModel):
    received: bool = True
    messages_normalized: int = 0
    messages_persisted: int = 0
    duplicates_ignored: int = 0
    statuses_processed: int = 0
    statuses_updated: int = 0
    ignored_events: int = 0
    auto_reply_sent: bool = False


def parse_meta_timestamp(value: str | None) -> datetime:
    if value and value.isdigit():
        try:
            return datetime.fromtimestamp(int(value), tz=UTC)
        except (OverflowError, OSError, ValueError):
            pass
    return datetime.now(UTC)


def should_apply_delivery_status_update(
    current_status: MessageDeliveryStatus | None,
    current_updated_at: datetime | None,
    incoming_status: MessageDeliveryStatus,
    incoming_updated_at: datetime,
) -> bool:
    if current_status is None:
        return True

    current_timestamp = _datetime_as_utc(current_updated_at)
    incoming_timestamp = _datetime_as_utc(incoming_updated_at)
    if incoming_timestamp is None:
        return False
    if current_timestamp is not None and incoming_timestamp < current_timestamp:
        return False

    if current_status == incoming_status:
        return current_timestamp is None or incoming_timestamp > current_timestamp

    if incoming_status == MessageDeliveryStatus.FAILED:
        return current_status in {
            MessageDeliveryStatus.PENDING,
            MessageDeliveryStatus.ACCEPTED,
            MessageDeliveryStatus.SENT,
        }

    # Meta status webhooks can arrive out of order; a newer success after FAILED is accepted
    # as recovery and clears the previous provider error metadata.
    if current_status == MessageDeliveryStatus.FAILED:
        return current_timestamp is None or incoming_timestamp > current_timestamp

    current_order = SUCCESS_STATUS_ORDER.get(current_status)
    incoming_order = SUCCESS_STATUS_ORDER.get(incoming_status)
    if current_order is None or incoming_order is None:
        return False

    return incoming_order > current_order


def _datetime_as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class WhatsAppWebhookProcessor:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def process(
        self,
        session: AsyncSession,
        messages: list[IncomingMessage],
        statuses: list[WhatsAppStatusNotification],
    ) -> WhatsAppWebhookProcessingResult:
        result = WhatsAppWebhookProcessingResult(
            messages_normalized=len(messages),
        )
        await record_audit_event(
            session,
            "WHATSAPP_WEBHOOK_RECEIVED",
            "webhook",
            "meta_whatsapp",
            metadata={"messages": len(messages), "statuses": len(statuses)},
            actor_type=AuditActorType.WEBHOOK,
        )

        for message in messages:
            if not self._phone_number_id_matches(message.metadata.get("phone_number_id")):
                result.ignored_events += 1
                await self._audit_phone_id_ignored(session, message.external_message_id)
                continue
            persisted = await self._persist_inbound_message(session, message)
            if persisted:
                result.messages_persisted += 1
            else:
                result.duplicates_ignored += 1

        for status in statuses:
            if not self._phone_number_id_matches(status.phone_number_id):
                result.ignored_events += 1
                await self._audit_phone_id_ignored(session, status.external_message_id)
                continue
            updated = await self._process_status(session, status)
            result.statuses_processed += 1
            if updated:
                result.statuses_updated += 1

        await session.commit()
        return result

    async def _persist_inbound_message(
        self,
        session: AsyncSession,
        incoming: IncomingMessage,
    ) -> bool:
        if incoming.content_type != ContentType.TEXT or not incoming.text:
            return False

        if incoming.external_message_id:
            existing = await session.scalar(
                select(Message).where(Message.external_message_id == incoming.external_message_id)
            )
            if existing is not None:
                await self._audit_duplicate(session, incoming.external_message_id)
                return False

        conversation = await self._find_or_create_conversation(
            session,
            external_user_ref=incoming.external_user_ref,
            event_id=incoming.event_id or self.settings.active_event_id,
        )
        conversation.last_message_at = parse_meta_timestamp(
            _metadata_string(incoming.metadata.get("timestamp"))
        )

        message = Message(
            conversation_id=conversation.id,
            external_message_id=incoming.external_message_id,
            direction=MessageDirection.INBOUND,
            sender_type=SenderType.PARTICIPANT,
            content_type=ContentType.TEXT,
            text_content=incoming.text,
            created_at=conversation.last_message_at,
        )

        try:
            async with session.begin_nested():
                session.add(message)
                await session.flush()
        except IntegrityError:
            await self._audit_duplicate(session, incoming.external_message_id)
            return False

        await record_audit_event(
            session,
            "WHATSAPP_MESSAGE_RECEIVED",
            "message",
            str(message.id),
            metadata={
                "channel": ChannelName.WHATSAPP.value,
                "has_external_message_id": incoming.external_message_id is not None,
            },
            actor_type=AuditActorType.WEBHOOK,
        )
        return True

    async def _find_or_create_conversation(
        self,
        session: AsyncSession,
        external_user_ref: str,
        event_id: UUID | None,
    ) -> Conversation:
        conditions = [
            Conversation.channel == ChannelName.WHATSAPP,
            Conversation.external_user_ref == external_user_ref,
        ]
        if event_id is None:
            conditions.append(Conversation.event_id.is_(None))
        else:
            conditions.append(Conversation.event_id == event_id)

        conversation = await session.scalar(select(Conversation).where(and_(*conditions)))
        if conversation is not None:
            return conversation

        conversation = Conversation(
            channel=ChannelName.WHATSAPP,
            external_user_ref=external_user_ref,
            event_id=event_id,
            state=ConversationState.AI_ACTIVE,
            human_takeover=False,
        )
        session.add(conversation)
        await session.flush()
        return conversation

    async def _process_status(
        self,
        session: AsyncSession,
        status: WhatsAppStatusNotification,
    ) -> bool:
        mapped_status = META_STATUS_MAP.get(status.status.lower())
        if mapped_status is None:
            return False

        message = await session.scalar(
            select(Message).where(Message.external_message_id == status.external_message_id)
        )
        if message is None:
            await record_audit_event(
                session,
                "WHATSAPP_STATUS_UNKNOWN_MESSAGE",
                "message",
                status.external_message_id,
                metadata={"status": status.status},
                actor_type=AuditActorType.WEBHOOK,
            )
            return False

        current = message.delivery_status
        status_updated_at = parse_meta_timestamp(status.timestamp)
        if not should_apply_delivery_status_update(
            current,
            message.delivery_status_updated_at,
            mapped_status,
            status_updated_at,
        ):
            return False

        message.delivery_status = mapped_status
        message.delivery_status_updated_at = status_updated_at
        if mapped_status == MessageDeliveryStatus.FAILED:
            message.provider_error_code = status.provider_error_code
            message.provider_error_message = status.provider_error_message
        else:
            message.provider_error_code = None
            message.provider_error_message = None

        await record_audit_event(
            session,
            "WHATSAPP_STATUS_UPDATED",
            "message",
            str(message.id),
            metadata={"status": mapped_status.value},
            actor_type=AuditActorType.WEBHOOK,
        )
        return True

    def _phone_number_id_matches(self, payload_phone_number_id: object) -> bool:
        configured = self.settings.meta_phone_number_id
        if not configured:
            return True
        return isinstance(payload_phone_number_id, str) and payload_phone_number_id == configured

    async def _audit_duplicate(
        self,
        session: AsyncSession,
        external_message_id: str | None,
    ) -> None:
        await record_audit_event(
            session,
            "WHATSAPP_DUPLICATE_IGNORED",
            "message",
            external_message_id or "missing_external_message_id",
            metadata={"has_external_message_id": external_message_id is not None},
            actor_type=AuditActorType.WEBHOOK,
        )

    async def _audit_phone_id_ignored(
        self,
        session: AsyncSession,
        external_message_id: str | None,
    ) -> None:
        await record_audit_event(
            session,
            "WHATSAPP_PHONE_ID_IGNORED",
            "webhook",
            external_message_id or "unknown_message",
            metadata={"reason": "phone_number_id_mismatch"},
            actor_type=AuditActorType.WEBHOOK,
        )


def _metadata_string(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None
