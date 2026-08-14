from datetime import date, datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.schemas.enums import EventStatus


class EventBase(BaseModel):
    slug: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1, max_length=240)
    description: str | None = None
    status: EventStatus = EventStatus.DRAFT
    venue: str | None = Field(default=None, max_length=240)
    start_date: date | None = None
    end_date: date | None = None
    registration_open: bool = False
    registration_deadline: datetime | None = None
    registration_url: HttpUrl | None = None
    is_active: bool = False

    @model_validator(mode="after")
    def validate_date_order(self) -> Self:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be earlier than start_date")
        return self


class EventCreate(EventBase):
    pass


class EventRead(EventBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
