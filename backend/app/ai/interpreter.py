from app.ai.base import AIProvider
from app.schemas.interpretation import InterpretationRequest, InterpretedMessage


class MessageInterpreter:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    async def interpret(self, request: InterpretationRequest) -> InterpretedMessage:
        return await self.provider.interpret_message(request)
