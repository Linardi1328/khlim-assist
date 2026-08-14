from collections import Counter

from pydantic import BaseModel

from app.ai.base import AIProvider
from app.policy.decision_engine import DecisionEngine
from app.policy.routing import route_reason
from app.schemas.decision import DecisionContext, KnowledgeEvidence
from app.schemas.enums import DecisionLevel
from app.schemas.interpretation import InterpretationRequest
from app.schemas.knowledge import EvaluationCase


class EvaluationCaseResult(BaseModel):
    case_id: str
    language_correct: bool
    primary_intent_correct: bool
    all_intents_correct: bool
    decision_correct: bool
    clarification_correct: bool
    pic_role_correct: bool
    predicted_language: str
    predicted_intents: list[str]
    predicted_decision: str
    predicted_pic_role: str | None


class EvaluationMetrics(BaseModel):
    total_cases: int
    language_correct_percent: float
    primary_intent_correct_percent: float
    all_expected_intents_correct_percent: float
    decision_level_correct_percent: float
    clarification_correct_percent: float
    pic_recommendation_correct_percent: float


class EvaluationReport(BaseModel):
    metrics: EvaluationMetrics
    cases: list[EvaluationCaseResult]


async def run_evaluation(
    cases: list[EvaluationCase],
    provider: AIProvider,
) -> EvaluationReport:
    results: list[EvaluationCaseResult] = []
    engine = DecisionEngine()
    for case in cases:
        interpreted = await provider.interpret_message(
            InterpretationRequest(message_text=case.text, channel="evaluation")
        )
        decision = engine.decide(interpreted, _synthetic_context_for_case(case))
        expected_pic = case.expected_pic_role
        predicted_pic = decision.assigned_pic_role
        if predicted_pic is None and decision.reason_code is not None:
            predicted_pic = route_reason(decision.reason_code)

        predicted_intents = [intent.type for intent in interpreted.intents]
        results.append(
            EvaluationCaseResult(
                case_id=case.id,
                language_correct=interpreted.primary_language == case.expected_language,
                primary_intent_correct=predicted_intents[0] == case.expected_intents[0],
                all_intents_correct=set(predicted_intents) == set(case.expected_intents),
                decision_correct=decision.level == case.expected_decision,
                clarification_correct=(
                    interpreted.requires_clarification == case.clarification_needed
                ),
                pic_role_correct=predicted_pic == expected_pic,
                predicted_language=interpreted.primary_language.value,
                predicted_intents=[intent.value for intent in predicted_intents],
                predicted_decision=decision.level.value,
                predicted_pic_role=predicted_pic.value if predicted_pic else None,
            )
        )

    return EvaluationReport(metrics=_metrics(results), cases=results)


def _synthetic_context_for_case(case: EvaluationCase) -> DecisionContext:
    if case.expected_decision == DecisionLevel.GREEN:
        return DecisionContext(
            evidence=[
                KnowledgeEvidence(
                    intent_type=intent,
                    approved_knowledge_found=True,
                    event_data_confirmed=True,
                    knowledge_source=f"synthetic_eval:{intent.value}",
                    value={"synthetic": True},
                    confirmed=True,
                )
                for intent in case.expected_intents
            ]
        )
    if case.expected_decision == DecisionLevel.YELLOW:
        requires_lookup = case.expected_pic_role is not None
        return DecisionContext(
            evidence=[
                KnowledgeEvidence(
                    intent_type=intent,
                    approved_knowledge_found=True,
                    event_data_confirmed=True,
                    requires_lookup=requires_lookup,
                    knowledge_source=f"synthetic_eval:{intent.value}",
                    value={"synthetic": True},
                    confirmed=True,
                )
                for intent in case.expected_intents
            ]
        )
    return DecisionContext(
        evidence=[
            KnowledgeEvidence(
                intent_type=intent,
                approved_knowledge_found=True,
                event_data_confirmed=True,
                requires_human=True,
                knowledge_source=f"synthetic_eval:{intent.value}",
                value={"synthetic": True},
                confirmed=True,
            )
            for intent in case.expected_intents
        ],
        requires_human_authority=True,
    )


def _metrics(results: list[EvaluationCaseResult]) -> EvaluationMetrics:
    total = len(results)
    counters = Counter(
        {
            "language": sum(result.language_correct for result in results),
            "primary_intent": sum(result.primary_intent_correct for result in results),
            "all_intents": sum(result.all_intents_correct for result in results),
            "decision": sum(result.decision_correct for result in results),
            "clarification": sum(result.clarification_correct for result in results),
            "pic": sum(result.pic_role_correct for result in results),
        }
    )
    return EvaluationMetrics(
        total_cases=total,
        language_correct_percent=_percent(counters["language"], total),
        primary_intent_correct_percent=_percent(counters["primary_intent"], total),
        all_expected_intents_correct_percent=_percent(counters["all_intents"], total),
        decision_level_correct_percent=_percent(counters["decision"], total),
        clarification_correct_percent=_percent(counters["clarification"], total),
        pic_recommendation_correct_percent=_percent(counters["pic"], total),
    )


def _percent(value: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round((value / total) * 100, 2)
