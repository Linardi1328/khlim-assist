from pydantic import BaseModel, Field

from app.schemas.enums import DecisionLevel, IntentType, PICRole, ReasonCode


class KnowledgeEvidence(BaseModel):
    intent_type: IntentType | None = None
    approved_knowledge_found: bool
    event_data_confirmed: bool
    requires_lookup: bool = False
    knowledge_source: str | None = None
    rule_source: str | None = None

    @property
    def has_named_source(self) -> bool:
        return bool(self.knowledge_source or self.rule_source)

    @property
    def supports_green(self) -> bool:
        return (
            self.approved_knowledge_found
            and self.event_data_confirmed
            and not self.requires_lookup
            and self.has_named_source
        )


class DecisionContext(BaseModel):
    evidence: list[KnowledgeEvidence] = Field(default_factory=list)
    requires_human_authority: bool = False

    def evidence_for_intent(self, intent_type: IntentType) -> list[KnowledgeEvidence]:
        intent_specific = [item for item in self.evidence if item.intent_type == intent_type]
        if intent_specific:
            return intent_specific
        return [item for item in self.evidence if item.intent_type is None]

    def green_ready_for(self, intent_types: list[IntentType]) -> bool:
        if self.requires_human_authority or not self.evidence:
            return False
        return all(
            any(evidence.supports_green for evidence in self.evidence_for_intent(intent_type))
            for intent_type in intent_types
        )

    @property
    def any_lookup_required(self) -> bool:
        return any(evidence.requires_lookup for evidence in self.evidence)

    @property
    def any_approved_knowledge_missing(self) -> bool:
        return any(not evidence.approved_knowledge_found for evidence in self.evidence)

    @property
    def any_event_data_unconfirmed(self) -> bool:
        return any(not evidence.event_data_confirmed for evidence in self.evidence)


class DecisionResult(BaseModel):
    level: DecisionLevel
    reason_code: ReasonCode | None = None
    assigned_pic_role: PICRole | None = None
    auto_reply_allowed: bool
    requires_human: bool
    clarification_fields: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
