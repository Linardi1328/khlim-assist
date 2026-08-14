from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings, get_settings
from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.messaging.meta_errors import MetaWhatsAppError
from app.messaging.phone_numbers import normalize_phone_number
from app.messaging.whatsapp_client import WhatsAppCloudClient
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


class WhatsAppOutboundService:
    def __init__(
        self,
        settings: Settings | None = None,
        client: WhatsAppCloudClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or WhatsAppCloudClient(self.settings)

    async def send_text(
        self,
        session: AsyncSession,
        to: str,
        text: str,
    ) -> Message:
        await record_audit_event(
            session,
            "WHATSAPP_OUTBOUND_REQUESTED",
            "conversation",
            "pending",
            metadata={"message_type": "text"},
            actor_type=AuditActorType.SYSTEM,
        )
        try:
            response = await self.client.send_text_message(to, text)
        except MetaWhatsAppError as exc:
            await self._audit_provider_error(session, exc)
            raise
        conversation = await self._find_or_create_conversation(session, normalize_phone_number(to))
        message = Message(
            conversation_id=conversation.id,
            external_message_id=response.provider_message_id,
            direction=MessageDirection.OUTBOUND,
            sender_type=SenderType.SYSTEM,
            content_type=ContentType.TEXT,
            text_content=text,
            delivery_status=MessageDeliveryStatus.ACCEPTED,
        )
        session.add(message)
        await session.flush()
        await record_audit_event(
            session,
            "WHATSAPP_OUTBOUND_ACCEPTED",
            "message",
            str(message.id),
            metadata={"has_external_message_id": True},
            actor_type=AuditActorType.SYSTEM,
        )
        await session.commit()
        return message

    async def send_template(
        self,
        session: AsyncSession,
        to: str,
        template_name: str,
        language_code: str,
    ) -> Message:
        await record_audit_event(
            session,
            "WHATSAPP_OUTBOUND_REQUESTED",
            "conversation",
            "pending",
            metadata={"message_type": "template"},
            actor_type=AuditActorType.SYSTEM,
        )
        try:
            response = await self.client.send_template_message(to, template_name, language_code)
        except MetaWhatsAppError as exc:
            await self._audit_provider_error(session, exc)
            raise
        conversation = await self._find_or_create_conversation(session, normalize_phone_number(to))
        message = Message(
            conversation_id=conversation.id,
            external_message_id=response.provider_message_id,
            direction=MessageDirection.OUTBOUND,
            sender_type=SenderType.SYSTEM,
            content_type=ContentType.TEXT,
            text_content=f"template:{template_name}:{language_code}",
            delivery_status=MessageDeliveryStatus.ACCEPTED,
        )
        session.add(message)
        await session.flush()
        await record_audit_event(
            session,
            "WHATSAPP_OUTBOUND_ACCEPTED",
            "message",
            str(message.id),
            metadata={"has_external_message_id": True},
            actor_type=AuditActorType.SYSTEM,
        )
        await session.commit()
        return message

    async def _find_or_create_conversation(
        self,
        session: AsyncSession,
        external_user_ref: str,
    ) -> Conversation:
        event_id = self.settings.active_event_id
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
        )
        session.add(conversation)
        await session.flush()
        return conversation

    async def _audit_provider_error(
        self,
        session: AsyncSession,
        exc: MetaWhatsAppError,
    ) -> None:
        await record_audit_event(
            session,
            "WHATSAPP_PROVIDER_ERROR",
            "provider",
            "meta_whatsapp",
            metadata={"error_type": type(exc).__name__},
            actor_type=AuditActorType.SYSTEM,
        )
        await session.commit()
