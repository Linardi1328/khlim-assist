from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.enums import ChannelName, ContentType

MetadataValue = str | int | float | bool | None


class IncomingMessage(BaseModel):
    channel: ChannelName
    external_user_ref: str
    external_message_id: str | None = None
    event_id: UUID | None = None
    content_type: ContentType
    text: str | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)


class OutgoingMessage(BaseModel):
    channel: ChannelName
    external_user_ref: str
    text: str
    conversation_id: UUID | None = None


class SendMessageResult(BaseModel):
    sent: bool
    provider_message_id: str | None = None
    error: str | None = None


class MessagingChannel(Protocol):
    async def receive_message(self, payload: object) -> list[IncomingMessage]:
        """Normalize an inbound provider payload into channel-neutral messages."""

    async def send_message(self, message: OutgoingMessage) -> SendMessageResult:
        """Send an outbound message through the provider."""
