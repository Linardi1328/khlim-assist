import json
import re
from pathlib import Path

from app.schemas.enums import DecisionLevel, FAQCategory, LanguageCode
from app.schemas.faq import FAQMasterFile
from app.schemas.knowledge import EscalationPolicyFile, EvaluationCasesFile, SampleEventFile

KNOWLEDGE_DIR = Path("knowledge")


def read_json(name: str) -> dict[str, object]:
    return json.loads((KNOWLEDGE_DIR / name).read_text(encoding="utf-8"))


def test_faq_master_validates_and_contains_required_categories() -> None:
    faq_master = FAQMasterFile.model_validate(read_json("faq_master.json"))
    categories = {entry.category for entry in faq_master.entries}

    assert {
        FAQCategory.REGISTRATION,
        FAQCategory.FEES,
        FAQCategory.TEAM_COMPOSITION,
        FAQCategory.ELIGIBILITY,
        FAQCategory.PLAYER_RESTRICTIONS,
        FAQCategory.SCHEDULE,
        FAQCategory.RULES,
        FAQCategory.CHECK_IN,
        FAQCategory.PAYMENT,
        FAQCategory.WITHDRAWAL,
        FAQCategory.MERCHANDISE,
        FAQCategory.TECHNICAL,
        FAQCategory.COMMERCIAL,
    }.issubset(categories)


def test_sample_event_validates_as_non_production_data() -> None:
    sample_event = SampleEventFile.model_validate(read_json("sample_event.json"))

    assert sample_event.sample_notice == "SAMPLE / NON-PRODUCTION DATA"
    assert (
        sample_event.player_count_rules.minimum_players
        <= sample_event.player_count_rules.maximum_players
    )


def test_escalation_policy_validates() -> None:
    policy = EscalationPolicyFile.model_validate(read_json("escalation_policy.json"))
    red_reasons = {
        reason.reason_code
        for reason in policy.reasons
        if reason.decision_level == DecisionLevel.RED
    }

    assert red_reasons
    assert all(not reason.auto_reply_allowed for reason in policy.reasons)


def test_evaluation_cases_validate_required_coverage() -> None:
    fixture = EvaluationCasesFile.model_validate(read_json("evaluation_cases.json"))
    languages = {case.expected_language for case in fixture.cases}
    decisions = {case.expected_decision for case in fixture.cases}
    multi_intent_cases = [case for case in fixture.cases if len(case.expected_intents) > 1]
    clarification_cases = [case for case in fixture.cases if case.clarification_needed]
    escalation_cases = [
        case for case in fixture.cases if case.expected_decision == DecisionLevel.RED
    ]

    assert len(fixture.cases) >= 40
    assert {
        LanguageCode.ENGLISH,
        LanguageCode.MALAY,
        LanguageCode.MANDARIN,
        LanguageCode.MIXED,
    }.issubset(languages)
    assert {DecisionLevel.GREEN, DecisionLevel.YELLOW, DecisionLevel.RED}.issubset(decisions)
    assert multi_intent_cases
    assert clarification_cases
    assert escalation_cases


def test_knowledge_files_do_not_contain_obvious_raw_pii() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in KNOWLEDGE_DIR.iterdir())

    assert not re.search(r"\b\d{8,}\b", combined)
    assert "passport number" not in combined.lower()
    assert "ic number" not in combined.lower()


def test_response_style_document_exists() -> None:
    style = (KNOWLEDGE_DIR / "response_style.md").read_text(encoding="utf-8")

    assert "Do not invent event facts" in style
    assert "Match the participant's language" in style
