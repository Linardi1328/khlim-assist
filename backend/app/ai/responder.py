from app.ai.base import AIProvider, GeneratedResponse, ResponseGenerationRequest


class ResponseGenerator:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    async def generate(self, request: ResponseGenerationRequest) -> GeneratedResponse:
        response = await self.provider.generate_response(request)
        return response.model_copy(update={"text": response.text.strip(), "should_send": False})
