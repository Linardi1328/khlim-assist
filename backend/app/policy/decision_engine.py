from app.policy.routing import route_reason
from app.schemas.decision import DecisionContext, DecisionResult
from app.schemas.enums import DecisionLevel, IntentType, ReasonCode
from app.schemas.interpretation import InterpretedMessage, MessageIntent

INTENT_REASON_CODES: dict[IntentType, ReasonCode] = {
    IntentType.REGISTRATION_STATUS: ReasonCode.REGISTRATION_STATUS_LOOKUP,
    IntentType.REGISTRATION_EXCEPTION: ReasonCode.REGISTRATION_EXCEPTION,
    IntentType.LATE_REGISTRATION: ReasonCode.REGISTRATION_EXCEPTION,
    IntentType.ELIGIBILITY_EXCEPTION: ReasonCode.ELIGIBILITY_EXCEPTION,
    IntentType.SCHEDULE_EXCEPTION: ReasonCode.SCHEDULE_EXCEPTION,
    IntentType.RULE_DISPUTE: ReasonCode.RULE_DISPUTE,
    IntentType.PAYMENT_VERIFICATION: ReasonCode.PAYMENT_VERIFICATION,
    IntentType.PAYMENT_STATUS: ReasonCode.PAYMENT_VERIFICATION,
    IntentType.REFUND_REQUEST: ReasonCode.REFUND_REQUEST,
    IntentType.REFUND: ReasonCode.REFUND_REQUEST,
    IntentType.OVERPAYMENT: ReasonCode.OVERPAYMENT,
    IntentType.WITHDRAWAL: ReasonCode.WITHDRAWAL,
    IntentType.WALKOVER_DISPUTE: ReasonCode.WALKOVER_DISPUTE,
    IntentType.MERCHANDISE_ORDER_LOOKUP: ReasonCode.MERCHANDISE_ORDER_LOOKUP,
    IntentType.MERCHANDISE_ORDER: ReasonCode.MERCHANDISE_ORDER_LOOKUP,
    IntentType.TECHNICAL_REGISTRATION_FAILURE: ReasonCode.TECHNICAL_REGISTRATION_FAILURE,
    IntentType.TECHNICAL_REGISTRATION: ReasonCode.TECHNICAL_REGISTRATION_FAILURE,
    IntentType.COMMERCIAL: ReasonCode.COMMERCIAL_ENQUIRY,
    IntentType.HUMAN_REQUEST: ReasonCode.HUMAN_REQUESTED,
    IntentType.UNKNOWN: ReasonCode.UNKNOWN_HIGH_RISK,
}

YELLOW_INTENTS = {
    IntentType.REGISTRATION_STATUS,
    IntentType.PAYMENT_VERIFICATION,
    IntentType.PAYMENT_STATUS,
    IntentType.MERCHANDISE_ORDER_LOOKUP,
    IntentType.MERCHANDISE_ORDER,
    IntentType.TECHNICAL_REGISTRATION_FAILURE,
    IntentType.TECHNICAL_REGISTRATION,
}

RED_INTENTS = {
    IntentType.REGISTRATION_EXCEPTION,
    IntentType.LATE_REGISTRATION,
    IntentType.ELIGIBILITY_EXCEPTION,
    IntentType.SCHEDULE_EXCEPTION,
    IntentType.RULE_DISPUTE,
    IntentType.REFUND_REQUEST,
    IntentType.REFUND,
    IntentType.OVERPAYMENT,
    IntentType.WITHDRAWAL,
    IntentType.WALKOVER_DISPUTE,
    IntentType.COMMERCIAL,
    IntentType.HUMAN_REQUEST,
    IntentType.UNKNOWN,
}

GREEN_INTENTS = {
    IntentType.REGISTRATION,
    IntentType.REGISTRATION_INFO,
    IntentType.FEES,
    IntentType.FEE,
    IntentType.EARLY_BIRD,
    IntentType.TEAM_COMPOSITION,
    IntentType.ELIGIBILITY,
    IntentType.PLAYER_RESTRICTIONS,
    IntentType.SCHEDULE,
    IntentType.RULES,
    IntentType.CHECK_IN,
    IntentType.PAYMENT,
    IntentType.MERCHANDISE_INFO,
    IntentType.GENERAL,
}

RED_REASON_PRIORITY = [
    IntentType.REFUND_REQUEST,
    IntentType.REFUND,
    IntentType.OVERPAYMENT,
    IntentType.REGISTRATION_EXCEPTION,
    IntentType.LATE_REGISTRATION,
    IntentType.ELIGIBILITY_EXCEPTION,
    IntentType.SCHEDULE_EXCEPTION,
    IntentType.WALKOVER_DISPUTE,
    IntentType.WITHDRAWAL,
    IntentType.RULE_DISPUTE,
    IntentType.COMMERCIAL,
    IntentType.HUMAN_REQUEST,
    IntentType.UNKNOWN,
]


class DecisionEngine:
    def decide(
        self,
        interpreted: InterpretedMessage,
        context: DecisionContext | None = None,
    ) -> DecisionResult:
        if interpreted.participant_requested_human:
            return self._red(ReasonCode.HUMAN_REQUESTED, ["participant requested a human"])

        red_reason = self._first_reason_for_intents(
            interpreted.intents,
            RED_INTENTS,
            priority=RED_REASON_PRIORITY,
        )
        if red_reason is not None:
            return self._red(red_reason, ["human authority is required"])

        clarification_fields = self._clarification_fields(interpreted)
        if interpreted.requires_clarification or clarification_fields:
            return DecisionResult(
                level=DecisionLevel.YELLOW,
                auto_reply_allowed=False,
                requires_human=False,
                clarification_fields=clarification_fields or interpreted.clarification_fields,
                notes=["clarification required before an answer can be trusted"],
            )

        yellow_reason = self._first_reason_for_intents(interpreted.intents, YELLOW_INTENTS)
        if yellow_reason is not None:
            return DecisionResult(
                level=DecisionLevel.YELLOW,
                reason_code=yellow_reason,
                assigned_pic_role=route_reason(yellow_reason),
                auto_reply_allowed=False,
                requires_human=False,
                notes=["trusted lookup is required before a final answer"],
            )

        if context is not None and context.requires_human_authority:
            return self._red(ReasonCode.UNKNOWN_HIGH_RISK, ["human authority is required"])

        if all(intent.type in GREEN_INTENTS for intent in interpreted.intents):
            if context is not None and context.green_ready_for(
                [intent.type for intent in interpreted.intents]
            ):
                return DecisionResult(
                    level=DecisionLevel.GREEN,
                    auto_reply_allowed=True,
                    requires_human=False,
                    notes=["approved knowledge or rules may answer this request"],
                )
            return self._yellow_for_missing_green_evidence(context)

        return self._red(ReasonCode.UNKNOWN_HIGH_RISK, ["unsupported request type"])

    def _clarification_fields(self, interpreted: InterpretedMessage) -> list[str]:
        fields = list(interpreted.clarification_fields)
        for intent in interpreted.intents:
            if intent.type == IntentType.ELIGIBILITY:
                if intent.entities.get("foreign_player") is True:
                    continue
                if "category" not in intent.entities and not intent.category:
                    fields.append("category")
                if "birth_year" not in intent.entities:
                    fields.append("birth_year")
        return sorted(set(fields))

    def _first_reason_for_intents(
        self,
        intents: list[MessageIntent],
        intent_types: set[IntentType],
        priority: list[IntentType] | None = None,
    ) -> ReasonCode | None:
        if priority is not None:
            by_type = {intent.type: intent for intent in intents if intent.type in intent_types}
            for intent_type in priority:
                intent = by_type.get(intent_type)
                if intent is not None:
                    return intent.reason_code or INTENT_REASON_CODES[intent.type]
        for intent in intents:
            if intent.type in intent_types:
                return intent.reason_code or INTENT_REASON_CODES[intent.type]
        return None

    def _red(self, reason_code: ReasonCode, notes: list[str]) -> DecisionResult:
        return DecisionResult(
            level=DecisionLevel.RED,
            reason_code=reason_code,
            assigned_pic_role=route_reason(reason_code),
            auto_reply_allowed=False,
            requires_human=True,
            notes=notes,
        )

    def _yellow_for_missing_green_evidence(
        self,
        context: DecisionContext | None,
    ) -> DecisionResult:
        notes = ["approved knowledge or confirmed event data is required before GREEN"]
        if context is None or not context.evidence:
            notes.append("no knowledge evidence was provided")
        else:
            if context.any_approved_knowledge_missing:
                notes.append("approved knowledge was not found")
            if context.any_event_data_unconfirmed:
                notes.append("event data is not confirmed")
            if context.any_lookup_required:
                notes.append("trusted lookup is required")

        return DecisionResult(
            level=DecisionLevel.YELLOW,
            auto_reply_allowed=False,
            requires_human=False,
            notes=notes,
        )
