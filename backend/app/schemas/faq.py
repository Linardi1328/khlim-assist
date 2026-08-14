from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.enums import AnswerSource, FAQCategory, FAQDisposition, FAQStatus


class FAQEntryBase(BaseModel):
    event_id: UUID | None = None
    faq_key: str = Field(min_length=2, max_length=160, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    category: FAQCategory
    generalized_question: str = Field(min_length=3)
    answer_source: AnswerSource
    static_answer: str | None = None
    auto_reply_allowed: bool = False
    requires_lookup: bool = False
    requires_human: bool = False
    status: FAQStatus = FAQStatus.DRAFT
    last_updated_at: datetime | None = None
    last_updated_by: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def validate_risk_flags(self) -> Self:
        if self.requires_human and self.auto_reply_allowed:
            raise ValueError("human-required FAQ entries cannot allow automatic replies")
        if self.requires_lookup and self.static_answer and self.auto_reply_allowed:
            raise ValueError("lookup-required FAQ entries cannot use static automatic answers")
        return self


class FAQEntryCreate(FAQEntryBase):
    pass


class FAQEntryRead(FAQEntryBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FAQSeedEntry(BaseModel):
    faq_key: str = Field(min_length=2)
    category: FAQCategory
    generalized_question: str = Field(min_length=3)
    normal_disposition: FAQDisposition
    answer_source: AnswerSource
    static_answer: str | None = None
    auto_reply_allowed: bool
    requires_lookup: bool
    requires_human: bool
    notes: str | None = None

    @model_validator(mode="after")
    def validate_disposition_flags(self) -> Self:
        if self.normal_disposition == FAQDisposition.AUTO and not self.auto_reply_allowed:
            raise ValueError("AUTO FAQ entries must allow automatic reply")
        if self.normal_disposition == FAQDisposition.LOOKUP and not self.requires_lookup:
            raise ValueError("LOOKUP FAQ entries must require lookup")
        if self.normal_disposition == FAQDisposition.HUMAN and not self.requires_human:
            raise ValueError("HUMAN FAQ entries must require human handling")
        return self


class FAQMasterFile(BaseModel):
    version: str
    description: str
    entries: list[FAQSeedEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def faq_keys_must_be_unique(self) -> Self:
        keys = [entry.faq_key for entry in self.entries]
        if len(keys) != len(set(keys)):
            raise ValueError("faq_key values must be unique")
        return self
