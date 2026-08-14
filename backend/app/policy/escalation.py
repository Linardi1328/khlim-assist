from pydantic import BaseModel

from app.policy.routing import route_reason
from app.schemas.enums import DecisionLevel, PICRole, ReasonCode


class EscalationDecision(BaseModel):
    reason_code: ReasonCode
    decision_level: DecisionLevel
    pic_role: PICRole
    auto_reply_allowed: bool
    requires_human: bool
    acknowledgement_type: str


def escalation_for_reason(reason_code: ReasonCode) -> EscalationDecision:
    level = DecisionLevel.YELLOW
    requires_human = False
    auto_reply_allowed = False
    acknowledgement = "lookup_acknowledgement"

    if reason_code in {
        ReasonCode.REGISTRATION_EXCEPTION,
        ReasonCode.REFUND_REQUEST,
        ReasonCode.OVERPAYMENT,
        ReasonCode.ELIGIBILITY_EXCEPTION,
        ReasonCode.RULE_DISPUTE,
        ReasonCode.SCHEDULE_EXCEPTION,
        ReasonCode.WITHDRAWAL,
        ReasonCode.WALKOVER_DISPUTE,
        ReasonCode.COMMERCIAL_ENQUIRY,
        ReasonCode.HUMAN_REQUESTED,
        ReasonCode.UNKNOWN_HIGH_RISK,
    }:
        level = DecisionLevel.RED
        requires_human = True
        acknowledgement = "human_handoff_acknowledgement"

    return EscalationDecision(
        reason_code=reason_code,
        decision_level=level,
        pic_role=route_reason(reason_code),
        auto_reply_allowed=auto_reply_allowed,
        requires_human=requires_human,
        acknowledgement_type=acknowledgement,
    )
