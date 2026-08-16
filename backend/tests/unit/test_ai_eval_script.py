import argparse
import json
from pathlib import Path

from app.schemas.knowledge import EvaluationCasesFile
from app.scripts.ai_eval import (
    DEFAULT_GROQ_OWNER_SMOKE_DELAY_SECONDS,
    OWNER_LIVE_SMOKE_CASE_IDS,
    _effective_delay_seconds,
    _select_cases,
)


def _fixture() -> EvaluationCasesFile:
    return EvaluationCasesFile.model_validate(
        json.loads(Path("knowledge/evaluation_cases.json").read_text(encoding="utf-8"))
    )


def test_owner_smoke_selects_representative_cases_in_stable_order() -> None:
    selected = _select_cases(_fixture().cases, owner_smoke=True)

    assert [case.id for case in selected] == list(OWNER_LIVE_SMOKE_CASE_IDS)


def test_full_eval_keeps_all_fixture_cases() -> None:
    fixture = _fixture()

    assert _select_cases(fixture.cases, owner_smoke=False) == fixture.cases


def test_groq_owner_smoke_defaults_to_conservative_pacing() -> None:
    args = argparse.Namespace(delay_seconds=None, owner_smoke=True, provider="groq")

    assert _effective_delay_seconds(args) == DEFAULT_GROQ_OWNER_SMOKE_DELAY_SECONDS


def test_explicit_delay_overrides_owner_smoke_default() -> None:
    args = argparse.Namespace(delay_seconds=5.0, owner_smoke=True, provider="groq")

    assert _effective_delay_seconds(args) == 5.0
