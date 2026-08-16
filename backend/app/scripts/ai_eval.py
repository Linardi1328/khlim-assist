import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.ai.base import AIProviderRateLimitError
from app.ai.evaluation import run_evaluation
from app.ai.providers import create_ai_provider, provider_choices
from app.config.settings import get_settings
from app.schemas.enums import AIProviderName
from app.schemas.knowledge import EvaluationCase, EvaluationCasesFile

OWNER_LIVE_SMOKE_CASE_IDS = (
    "en_fee_u16",
    "zh_payment",
    "ms_late_register",
    "mixed_multi_intent",
    "clarify_category",
    "unknown_high_risk",
)
DEFAULT_GROQ_OWNER_SMOKE_DELAY_SECONDS = 30.0


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
    parser.add_argument(
        "--owner-smoke",
        action="store_true",
        help=(
            "Run the representative owner-live subset instead of the full corpus. "
            "For Groq this also enables conservative free-tier pacing unless overridden."
        ),
    )
    parser.add_argument(
        "--delay-seconds",
        type=_non_negative_float,
        default=None,
        help="Optional delay between live evaluation cases.",
    )
    return parser.parse_args()


def _non_negative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def _select_cases(cases: list[EvaluationCase], owner_smoke: bool) -> list[EvaluationCase]:
    if not owner_smoke:
        return cases

    by_id = {case.id: case for case in cases}
    missing = [case_id for case_id in OWNER_LIVE_SMOKE_CASE_IDS if case_id not in by_id]
    if missing:
        raise ValueError(f"Owner smoke cases missing from evaluation fixture: {', '.join(missing)}")
    return [by_id[case_id] for case_id in OWNER_LIVE_SMOKE_CASE_IDS]


def _effective_delay_seconds(args: argparse.Namespace) -> float:
    if args.delay_seconds is not None:
        return float(args.delay_seconds)
    if args.owner_smoke and args.provider == AIProviderName.GROQ.value:
        return DEFAULT_GROQ_OWNER_SMOKE_DELAY_SECONDS
    return 0.0


def _print_progress(index: int, total: int, case: EvaluationCase) -> None:
    print(f"[{index}/{total}] {case.id}", flush=True)


async def main() -> None:
    args = parse_args()
    fixture = EvaluationCasesFile.model_validate(
        json.loads(Path(args.cases).read_text(encoding="utf-8"))
    )
    try:
        cases = _select_cases(fixture.cases, args.owner_smoke)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    settings = get_settings()
    provider = create_ai_provider(settings, args.provider)
    delay_seconds = _effective_delay_seconds(args)

    if args.owner_smoke:
        print(f"Owner live smoke cases: {len(cases)}", flush=True)
    if delay_seconds > 0:
        print(f"Inter-case delay: {delay_seconds:g}s", flush=True)

    try:
        report = await run_evaluation(
            cases,
            provider,
            progress_callback=_print_progress,
            delay_seconds=delay_seconds,
        )
    except AIProviderRateLimitError as exc:
        print(f"Rate limit reached before evaluation completed: {exc}", file=sys.stderr)
        print(
            "Owner live evaluation is incomplete. Increase --delay-seconds or check the "
            "provider account limits before rerunning.",
            file=sys.stderr,
        )
        raise SystemExit(2) from None

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
