from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import (
    ContentType,
    LanguageCode,
    MessageDeliveryStatus,
    MessageDirection,
    SenderType,
)


class MessageBase(BaseModel):
    conversation_id: UUID
    external_message_id: str | None = Field(default=None, max_length=240)
    direction: MessageDirection
    sender_type: SenderType
    language: LanguageCode | None = None
    content_type: ContentType = ContentType.TEXT
    text_content: str | None = None
    delivery_status: MessageDeliveryStatus | None = None
    delivery_status_updated_at: datetime | None = None
    provider_error_code: str | None = Field(default=None, max_length=80)
    provider_error_message: str | None = Field(default=None, max_length=500)


class MessageCreate(MessageBase):
    pass


class MessageRead(MessageBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
