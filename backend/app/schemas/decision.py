from pydantic import BaseModel, Field

from app.schemas.enums import DecisionLevel, PICRole, ReasonCode


class DecisionResult(BaseModel):
    level: DecisionLevel
    reason_code: ReasonCode | None = None
    assigned_pic_role: PICRole | None = None
    auto_reply_allowed: bool
    requires_human: bool
    clarification_fields: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
