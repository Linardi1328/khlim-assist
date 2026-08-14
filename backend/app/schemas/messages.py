from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import ContentType, LanguageCode, MessageDirection, SenderType


class MessageBase(BaseModel):
    conversation_id: UUID
    external_message_id: str | None = Field(default=None, max_length=240)
    direction: MessageDirection
    sender_type: SenderType
    language: LanguageCode | None = None
    content_type: ContentType = ContentType.TEXT
    text_content: str | None = None


class MessageCreate(MessageBase):
    pass


class MessageRead(MessageBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
