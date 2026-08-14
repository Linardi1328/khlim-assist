from datetime import date, datetime
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.enums import RuleStatus


class EventRuleBase(BaseModel):
    event_id: UUID
    category: str = Field(min_length=1, max_length=80)
    rule_type: str = Field(min_length=1, max_length=120)
    value: dict[str, Any] = Field(min_length=1)
    status: RuleStatus = RuleStatus.ACTIVE
    effective_from: date | None = None
    effective_until: date | None = None

    @model_validator(mode="after")
    def validate_effective_dates(self) -> Self:
        if (
            self.effective_from
            and self.effective_until
            and self.effective_until < self.effective_from
        ):
            raise ValueError("effective_until cannot be earlier than effective_from")
        return self


class EventRuleCreate(EventRuleBase):
    pass


class EventRuleRead(EventRuleBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
