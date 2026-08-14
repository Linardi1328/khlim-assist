from openai import AsyncOpenAI

from app.ai.base import AIProviderUnavailable, GeneratedResponse, ResponseGenerationRequest
from app.config.settings import Settings, get_settings
from app.schemas.interpretation import InterpretationRequest, InterpretedMessage


class OpenAIProvider:
    """Lazy OpenAI SDK wrapper.

    The SDK client is not constructed until an AI method is called, so application startup and
    tests do not require network access or credentials.
    """

    def __init__(self, settings: Settings | None = None, model: str = "gpt-4o-mini") -> None:
        self.settings = settings or get_settings()
        self.model = model
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        if not self.settings.openai_api_key:
            raise AIProviderUnavailable("OPENAI_API_KEY is required for OpenAI AI calls.")
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        return self._client

    async def interpret_message(self, request: InterpretationRequest) -> InterpretedMessage:
        completion = await self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Return only JSON matching the KHLIM Assist InterpretedMessage schema. "
                        "Do not decide permissions; only interpret the participant message."
                    ),
                },
                {"role": "user", "content": request.message_text},
            ],
        )
        content = completion.choices[0].message.content
        if not content:
            raise AIProviderUnavailable("OpenAI returned an empty interpretation response.")
        return InterpretedMessage.model_validate_json(content)

    async def generate_response(self, request: ResponseGenerationRequest) -> GeneratedResponse:
        completion = await self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Write concise KHLIM-style participant support text. "
                        "Do not invent event facts and do not claim a lookup was completed."
                    ),
                },
                {
                    "role": "user",
                    "content": "\n\n".join(request.knowledge_snippets),
                },
            ],
        )
        content = completion.choices[0].message.content or ""
        return GeneratedResponse(text=content.strip(), should_send=False)
