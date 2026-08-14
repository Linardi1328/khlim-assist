from app.config.settings import Settings
from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.messaging.whatsapp_client import WhatsAppSendResponse
from app.schemas.enums import (
    ChannelName,
    MessageDeliveryStatus,
    MessageDirection,
    SenderType,
)
from app.services.whatsapp_outbound import WhatsAppOutboundService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class FakeWhatsAppClient:
    async def send_text_message(self, to: str, text: str) -> WhatsAppSendResponse:
        return WhatsAppSendResponse(provider_message_id="wamid.synthetic_manual_text_1")

    async def send_template_message(
        self,
        to: str,
        template_name: str,
        language_code: str,
    ) -> WhatsAppSendResponse:
        return WhatsAppSendResponse(provider_message_id="wamid.synthetic_manual_template_1")


async def test_outbound_text_persistence(db_session: AsyncSession) -> None:
    service = WhatsAppOutboundService(Settings(), client=FakeWhatsAppClient())  # type: ignore[arg-type]

    message = await service.send_text(db_session, "+1 555-000-0001", "KHLIM sandbox test")

    conversations = list(await db_session.scalars(select(Conversation)))
    messages = list(await db_session.scalars(select(Message)))
    assert len(conversations) == 1
    assert conversations[0].channel == ChannelName.WHATSAPP
    assert conversations[0].external_user_ref == "15550000001"
    assert len(messages) == 1
    assert message.external_message_id == "wamid.synthetic_manual_text_1"
    assert message.direction == MessageDirection.OUTBOUND
    assert message.sender_type == SenderType.SYSTEM
    assert message.delivery_status == MessageDeliveryStatus.ACCEPTED


async def test_outbound_template_persistence(db_session: AsyncSession) -> None:
    service = WhatsAppOutboundService(Settings(), client=FakeWhatsAppClient())  # type: ignore[arg-type]

    message = await service.send_template(db_session, "15550000001", "hello_world", "en_US")

    assert message.external_message_id == "wamid.synthetic_manual_template_1"
    assert message.direction == MessageDirection.OUTBOUND
    assert message.sender_type == SenderType.SYSTEM
    assert message.delivery_status == MessageDeliveryStatus.ACCEPTED
