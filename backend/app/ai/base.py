from typing import Protocol

from pydantic import BaseModel, Field

from app.schemas.interpretation import InterpretationRequest, InterpretedMessage


class AIProviderUnavailable(RuntimeError):
    """Raised when an AI action is requested but the provider is not configured."""


class ResponseGenerationRequest(BaseModel):
    interpreted_message: InterpretedMessage
    knowledge_snippets: list[str] = Field(default_factory=list)
    response_language: str


class GeneratedResponse(BaseModel):
    text: str
    should_send: bool = False


class AIProvider(Protocol):
    async def interpret_message(self, request: InterpretationRequest) -> InterpretedMessage:
        """Return structured interpretation for a participant message."""

    async def generate_response(self, request: ResponseGenerationRequest) -> GeneratedResponse:
        """Generate response text without deciding whether the system is allowed to send it."""
