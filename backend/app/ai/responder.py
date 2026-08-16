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
        return response.model_copy(update={"text": response.text.strip(), "should_send": False})


def _human_review_draft(response_language: str) -> str:
    return _HUMAN_REVIEW_DRAFTS.get(
        response_language,
        _HUMAN_REVIEW_DRAFTS[LanguageCode.ENGLISH.value],
    )
