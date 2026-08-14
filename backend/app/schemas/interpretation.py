from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.schemas.enums import IntentType, LanguageCode, LanguageMode, ReasonCode

EntityValue = str | int | float | bool | None


class MessageIntent(BaseModel):
    type: IntentType
    category: str | None = None
    entities: dict[str, EntityValue] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reason_code: ReasonCode | None = None


class InterpretedMessage(BaseModel):
    primary_language: LanguageCode
    language_mode: LanguageMode
    intents: list[MessageIntent] = Field(min_length=1)
    requires_clarification: bool = False
    clarification_fields: list[str] = Field(default_factory=list)
    participant_requested_human: bool = False

    @model_validator(mode="after")
    def validate_clarification_fields(self) -> Self:
        if self.requires_clarification and not self.clarification_fields:
            raise ValueError(
                "clarification_fields are required when requires_clarification is true"
            )
        return self


class InterpretationContextMessage(BaseModel):
    role: str = Field(pattern=r"^(participant|khlim|system)$")
    text: str = Field(min_length=1)


class InterpretationRequest(BaseModel):
    message_text: str = Field(min_length=1)
    channel: str
    event_id: str | None = None
    conversation_id: str | None = None
    recent_messages: list[InterpretationContextMessage] = Field(default_factory=list)
