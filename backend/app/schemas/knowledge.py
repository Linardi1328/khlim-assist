from datetime import date, datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.schemas.enums import (
    AnswerSource,
    DecisionLevel,
    FAQCategory,
    FAQDisposition,
    IntentType,
    LanguageCode,
    PICRole,
    ReasonCode,
)
from app.schemas.faq import FAQMasterFile


class CategoryFee(BaseModel):
    category: str
    amount_myr: int = Field(ge=0)
    label: str | None = None


class CategoryPlayingDate(BaseModel):
    category: str
    playing_date: date


class EligibilityRuleSeed(BaseModel):
    category: str
    rule_type: str
    value: dict[str, Any]


class PlayerCountRules(BaseModel):
    minimum_players: int = Field(ge=1)
    maximum_players: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_player_count_order(self) -> Self:
        if self.maximum_players < self.minimum_players:
            raise ValueError("maximum_players cannot be lower than minimum_players")
        return self


class ForeignPlayerRules(BaseModel):
    permitted: bool
    maximum_foreign_players: int | None = Field(default=None, ge=0)
    notes: str | None = None


class CheckInRules(BaseModel):
    whole_team_required: bool
    one_player_can_check_in: bool
    notes: str


class MerchandiseSample(BaseModel):
    included_in_registration: bool
    preorder_deadline: datetime | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)
    delivery_notes: str | None = None


class SampleEventFile(BaseModel):
    sample_notice: Literal["SAMPLE / NON-PRODUCTION DATA"]
    event_name: str
    venue: str
    event_dates: list[date] = Field(min_length=1)
    registration_open: bool
    registration_deadline: datetime
    registration_url: HttpUrl
    category_fees: list[CategoryFee]
    category_playing_dates: list[CategoryPlayingDate]
    player_count_rules: PlayerCountRules
    eligibility_rules: list[EligibilityRuleSeed]
    foreign_player_rules: ForeignPlayerRules
    check_in_rules: CheckInRules
    merchandise: MerchandiseSample
    notes: str


class EscalationPolicyReason(BaseModel):
    reason_code: ReasonCode
    decision_level: DecisionLevel
    pic_role: PICRole
    auto_reply_allowed: bool
    requires_human: bool
    suggested_acknowledgement_type: str


class EscalationPolicyFile(BaseModel):
    version: str
    reasons: list[EscalationPolicyReason] = Field(min_length=1)

    @model_validator(mode="after")
    def reason_codes_must_be_unique(self) -> Self:
        codes = [reason.reason_code for reason in self.reasons]
        if len(codes) != len(set(codes)):
            raise ValueError("reason_code values must be unique")
        return self


class EvaluationCase(BaseModel):
    id: str
    text: str = Field(min_length=1)
    expected_language: LanguageCode
    expected_intents: list[IntentType] = Field(min_length=1)
    expected_decision: DecisionLevel
    expected_pic_role: PICRole | None = None
    clarification_needed: bool
    notes: str | None = None


class EvaluationCasesFile(BaseModel):
    version: str
    description: str
    cases: list[EvaluationCase] = Field(min_length=40)

    @model_validator(mode="after")
    def case_ids_must_be_unique(self) -> Self:
        case_ids = [case.id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("evaluation case ids must be unique")
        return self


__all__ = [
    "AnswerSource",
    "EscalationPolicyFile",
    "EvaluationCasesFile",
    "FAQCategory",
    "FAQDisposition",
    "FAQMasterFile",
    "SampleEventFile",
]
