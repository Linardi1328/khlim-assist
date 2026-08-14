from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import ChannelName, ConversationState, LanguageCode


class ConversationBase(BaseModel):
    channel: ChannelName
    external_user_ref: str = Field(min_length=1, max_length=240)
    event_id: UUID | None = None
    preferred_language: LanguageCode | None = None
    state: ConversationState = ConversationState.AI_ACTIVE
    assigned_pic_role: str | None = Field(default=None, max_length=80)
    human_takeover: bool = False
    last_message_at: datetime | None = None


class ConversationCreate(ConversationBase):
    pass


class ConversationRead(ConversationBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
