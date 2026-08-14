from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import HandoffPriority, HandoffStatus, ReasonCode


class HandoffCaseBase(BaseModel):
    conversation_id: UUID
    event_id: UUID | None = None
    reason_code: ReasonCode
    category: str | None = Field(default=None, max_length=80)
    summary: str = Field(min_length=1)
    assigned_pic_role: str = Field(min_length=1, max_length=80)
    priority: HandoffPriority = HandoffPriority.NORMAL
    status: HandoffStatus = HandoffStatus.OPEN
    assigned_at: datetime | None = None
    resolved_at: datetime | None = None


class HandoffCaseCreate(HandoffCaseBase):
    pass


class HandoffCaseRead(HandoffCaseBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
