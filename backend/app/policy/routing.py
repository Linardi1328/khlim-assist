from app.schemas.enums import PICRole, ReasonCode

REASON_CODE_TO_PIC_ROLE: dict[ReasonCode, PICRole] = {
    ReasonCode.REGISTRATION_EXCEPTION: PICRole.REGISTRATION,
    ReasonCode.REGISTRATION_STATUS_LOOKUP: PICRole.REGISTRATION,
    ReasonCode.PAYMENT_VERIFICATION: PICRole.FINANCE,
    ReasonCode.REFUND_REQUEST: PICRole.FINANCE,
    ReasonCode.OVERPAYMENT: PICRole.FINANCE,
    ReasonCode.ELIGIBILITY_EXCEPTION: PICRole.COMPETITION,
    ReasonCode.RULE_DISPUTE: PICRole.COMPETITION,
    ReasonCode.SCHEDULE_EXCEPTION: PICRole.TOURNAMENT_DIRECTOR,
    ReasonCode.WITHDRAWAL: PICRole.TOURNAMENT_DIRECTOR,
    ReasonCode.WALKOVER_DISPUTE: PICRole.TOURNAMENT_DIRECTOR,
    ReasonCode.MERCHANDISE_ORDER_LOOKUP: PICRole.MERCHANDISE,
    ReasonCode.TECHNICAL_REGISTRATION_FAILURE: PICRole.REGISTRATION,
    ReasonCode.COMMERCIAL_ENQUIRY: PICRole.COMMERCIAL,
    ReasonCode.HUMAN_REQUESTED: PICRole.GENERAL_ADMIN,
    ReasonCode.UNKNOWN_HIGH_RISK: PICRole.GENERAL_ADMIN,
}

TEXT_ROUTING_RULES: tuple[tuple[tuple[str, ...], PICRole], ...] = (
    (("late registration", "registration exception", "registration failure"), PICRole.REGISTRATION),
    (("payment confirmation", "refund", "overpayment"), PICRole.FINANCE),
    (("eligibility exception", "rule dispute"), PICRole.COMPETITION),
    (
        ("schedule exception", "withdrawal", "walkover"),
        PICRole.TOURNAMENT_DIRECTOR,
    ),
    (("venue", "operations issue", "operations"), PICRole.OPERATIONS),
    (("merchandise", "jersey", "shirt"), PICRole.MERCHANDISE),
    (("vendor", "booth", "commercial"), PICRole.COMMERCIAL),
)


def route_reason(reason_code: ReasonCode | None) -> PICRole:
    if reason_code is None:
        return PICRole.GENERAL_ADMIN
    return REASON_CODE_TO_PIC_ROLE.get(reason_code, PICRole.GENERAL_ADMIN)


def route_text(description: str) -> PICRole:
    normalized = description.lower()
    for keywords, role in TEXT_ROUTING_RULES:
        if any(keyword in normalized for keyword in keywords):
            return role
    return PICRole.GENERAL_ADMIN
