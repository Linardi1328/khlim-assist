import re

from app.ai.base import AIProvider, GeneratedResponse, ResponseGenerationRequest
from app.schemas.enums import LanguageCode

_HUMAN_REVIEW_DRAFTS = {
    LanguageCode.ENGLISH.value: (
        "Thanks for checking. This needs review by our team before we can confirm anything."
    ),
    LanguageCode.MALAY.value: (
        "Terima kasih bertanya. Perkara ini perlu disemak oleh pasukan kami sebelum kami boleh "
        "sahkan apa-apa."
    ),
    LanguageCode.MANDARIN.value: "谢谢你的询问。这需要由我们的团队审核后才能确认。",
}

_UNVERIFIED_ACTION_MARKERS = (
    "i'll forward",
    "i will forward",
    "we'll forward",
    "we will forward",
    "i'll get back",
    "i will get back",
    "we'll get back",
    "we will get back",
    "i've forwarded",
    "i have forwarded",
    "we've forwarded",
    "we have forwarded",
)

_UNSUPPORTED_POLICY_MARKERS = (
    "can't be changed",
    "can’t be changed",
    "cannot be changed",
    "can't be modified",
    "can’t be modified",
    "cannot be modified",
    "non-negotiable",
    "tidak boleh diubah",
    "tak boleh diubah",
    "tidak boleh ditukar",
    "tak boleh ditukar",
    "不能更改",
    "不可更改",
    "不能修改",
    "不可修改",
)

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?。！？])\s*")


class ResponseGenerator:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    async def generate(self, request: ResponseGenerationRequest) -> GeneratedResponse:
        if request.decision_result.requires_human:
            # Phase 2 does not perform handoffs. Do not let a model imply that a PIC was
            # contacted, a request was forwarded, or a follow-up was scheduled when none occurred.
            self.provider.response_metadata = None
            return GeneratedResponse(
                text=_human_review_draft(request.response_language),
                should_send=False,
            )

        response = await self.provider.generate_response(request)
        return response.model_copy(
            update={
                "text": _sanitize_provider_draft(response.text.strip(), request),
                "should_send": False,
            }
        )


def _human_review_draft(response_language: str) -> str:
    return _HUMAN_REVIEW_DRAFTS.get(
        response_language,
        _HUMAN_REVIEW_DRAFTS[LanguageCode.ENGLISH.value],
    )


def _sanitize_provider_draft(text: str, request: ResponseGenerationRequest) -> str:
    evidence_text = _approved_evidence_text(request)
    sentences = [part.strip() for part in _SENTENCE_BOUNDARY.split(text) if part.strip()]
    kept: list[str] = []

    for sentence in sentences:
        normalized = sentence.casefold()
        if any(marker in normalized for marker in _UNVERIFIED_ACTION_MARKERS):
            continue
        if any(
            marker in normalized and marker not in evidence_text
            for marker in _UNSUPPORTED_POLICY_MARKERS
        ):
            continue
        kept.append(sentence)

    sanitized = " ".join(kept).strip()
    return sanitized or _safe_grounding_fallback(request)


def _approved_evidence_text(request: ResponseGenerationRequest) -> str:
    fragments: list[str] = []
    for result in request.knowledge_results:
        if not result.found:
            continue
        fragments.append(str(result.value))
        fragments.extend(result.notes)
    return " ".join(fragments).casefold()


def _safe_grounding_fallback(request: ResponseGenerationRequest) -> str:
    for result in request.knowledge_results:
        if not result.found or not result.confirmed:
            continue
        if isinstance(result.value, str) and result.value.strip():
            return result.value.strip()
        if isinstance(result.value, dict):
            amount = result.value.get("amount_myr")
            if isinstance(amount, int | float) and not isinstance(amount, bool):
                return _fee_fallback(request, amount)

    return "I can only confirm the approved information currently available for this request."


def _fee_fallback(request: ResponseGenerationRequest, amount: int | float) -> str:
    amount_text = f"{amount:g}"
    category = next(
        (
            intent.category
            for intent in request.interpreted_message.intents
            if intent.category is not None
        ),
        None,
    )
    category_text = f" for {category}" if category else ""

    if request.response_language == LanguageCode.MALAY.value:
        return f"Yuran pendaftaran{category_text} yang disahkan ialah RM{amount_text}."
    if request.response_language == LanguageCode.MANDARIN.value:
        category_zh = f"（{category}）" if category else ""
        return f"已确认的报名费{category_zh}是 RM{amount_text}。"
    return f"The approved registration fee{category_text} is RM{amount_text}."
