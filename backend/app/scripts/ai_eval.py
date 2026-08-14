import argparse
import asyncio
import json
from pathlib import Path

from app.ai.evaluation import run_evaluation
from app.ai.providers import create_ai_provider, provider_choices
from app.config.settings import get_settings
from app.schemas.enums import AIProviderName
from app.schemas.knowledge import EvaluationCasesFile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 2 structured evaluation fixtures.")
    parser.add_argument(
        "--provider",
        choices=provider_choices(),
        default=AIProviderName.FAKE.value,
        help="Provider for interpretation. fake is deterministic and CI-safe.",
    )
    parser.add_argument(
        "--cases",
        default="knowledge/evaluation_cases.json",
        help="Path to evaluation_cases.json.",
    )
    parser.add_argument(
        "--json-report",
        default=None,
        help="Optional local JSON report path. Use artifacts/ for ignored local output.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    fixture = EvaluationCasesFile.model_validate(
        json.loads(Path(args.cases).read_text(encoding="utf-8"))
    )
    settings = get_settings()
    provider = create_ai_provider(settings, args.provider)
    report = await run_evaluation(fixture.cases, provider)

    print(f"Total cases: {report.metrics.total_cases}")
    print(f"Language correct %: {report.metrics.language_correct_percent}")
    print(f"Primary intent correct %: {report.metrics.primary_intent_correct_percent}")
    print(f"All expected intents correct %: {report.metrics.all_expected_intents_correct_percent}")
    print(f"GREEN/YELLOW/RED correct %: {report.metrics.decision_level_correct_percent}")
    print(f"Clarification correct %: {report.metrics.clarification_correct_percent}")
    print(f"PIC recommendation correct %: {report.metrics.pic_recommendation_correct_percent}")

    if args.json_report:
        report_path = Path(args.json_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        print(f"JSON report: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
