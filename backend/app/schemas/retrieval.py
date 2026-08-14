from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.decision import JsonValue, KnowledgeEvidence
from app.schemas.enums import IntentType
from app.schemas.interpretation import InterpretedMessage


class KnowledgeQuery(BaseModel):
    interpreted_message: InterpretedMessage
    conversation_id: UUID | None = None
    event_id: UUID | None = None


class KnowledgeResult(BaseModel):
    intent_type: IntentType
    found: bool
    source_type: str | None = None
    source_identifier: str | None = None
    event_id: UUID | None = None
    faq_key: str | None = None
    rule_type: str | None = None
    value: JsonValue = None
    confirmed: bool = False
    requires_lookup: bool = False
    requires_human: bool = False
    last_updated_at: datetime | None = None
    notes: list[str] = Field(default_factory=list)

    @property
    def source_label(self) -> str | None:
        if self.source_type and self.source_identifier:
            return f"{self.source_type}:{self.source_identifier}"
        return self.source_identifier

    def to_evidence(self) -> KnowledgeEvidence:
        source_label = self.source_label
        return KnowledgeEvidence(
            intent_type=self.intent_type,
            approved_knowledge_found=self.found,
            event_data_confirmed=self.confirmed,
            requires_lookup=self.requires_lookup,
            requires_human=self.requires_human,
            knowledge_source=source_label,
            rule_source=source_label if self.rule_type else None,
            source_type=self.source_type,
            source_identifier=self.source_identifier,
            event_id=str(self.event_id) if self.event_id else None,
            faq_key=self.faq_key,
            rule_type=self.rule_type,
            value=self.value,
            confirmed=self.confirmed,
            last_updated_at=self.last_updated_at.isoformat() if self.last_updated_at else None,
        )
