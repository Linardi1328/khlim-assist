from app.ai.evaluation import run_evaluation
from app.ai.fake import FakeAIProvider
from app.schemas.enums import DecisionLevel, IntentType, LanguageCode, PICRole
from app.schemas.knowledge import EvaluationCase


async def test_evaluation_runner_reports_structured_metrics() -> None:
    report = await run_evaluation(
        [
            EvaluationCase(
                id="eval_fee",
                text="How much is U16?",
                expected_language=LanguageCode.ENGLISH,
                expected_intents=[IntentType.FEE],
                expected_decision=DecisionLevel.GREEN,
                expected_pic_role=None,
                clarification_needed=False,
            ),
            EvaluationCase(
                id="eval_payment",
                text="Have you received my payment?",
                expected_language=LanguageCode.ENGLISH,
                expected_intents=[IntentType.PAYMENT_STATUS],
                expected_decision=DecisionLevel.YELLOW,
                expected_pic_role=PICRole.FINANCE,
                clarification_needed=False,
            ),
            EvaluationCase(
                id="eval_exception",
                text="My player is one month overage, can make exception?",
                expected_language=LanguageCode.ENGLISH,
                expected_intents=[IntentType.ELIGIBILITY_EXCEPTION],
                expected_decision=DecisionLevel.RED,
                expected_pic_role=PICRole.COMPETITION,
                clarification_needed=False,
            ),
        ],
        FakeAIProvider(),
    )

    assert report.metrics.total_cases == 3
    assert report.metrics.language_correct_percent == 100
    assert report.metrics.primary_intent_correct_percent == 100
    assert report.metrics.decision_level_correct_percent == 100
    assert report.metrics.pic_recommendation_correct_percent == 100
