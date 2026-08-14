from typing import Protocol

from pydantic import BaseModel, Field

from app.schemas.decision import DecisionResult
from app.schemas.interpretation import InterpretationRequest, InterpretedMessage
from app.schemas.retrieval import KnowledgeResult


class AIProviderError(RuntimeError):
    """Base error for AI provider failures."""


class AIProviderUnavailable(AIProviderError):
    """Raised when an AI action is requested but the provider is not configured."""


class AIProviderAuthenticationError(AIProviderError):
    """Raised when the provider rejects credentials."""


class AIProviderRateLimitError(AIProviderError):
    """Raised when the provider rate-limits a request."""


class AIProviderTimeoutError(AIProviderError):
    """Raised when the provider request times out."""


class AIProviderRequestError(AIProviderError):
    """Raised when the provider rejects or cannot complete a request."""


class AIProviderResponseError(AIProviderError):
    """Raised when the provider response cannot be safely parsed."""


class AIProviderCallMetadata(BaseModel):
    provider_request_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class ResponseGenerationRequest(BaseModel):
    interpreted_message: InterpretedMessage
    decision_result: DecisionResult
    knowledge_results: list[KnowledgeResult] = Field(default_factory=list)
    conversation_context: list[str] = Field(default_factory=list)
    response_language: str
    participant_text: str


class GeneratedResponse(BaseModel):
    text: str
    should_send: bool = False


class AIProvider(Protocol):
    interpretation_metadata: AIProviderCallMetadata | None
    response_metadata: AIProviderCallMetadata | None

    async def interpret_message(self, request: InterpretationRequest) -> InterpretedMessage:
        """Return structured interpretation for a participant message."""

    async def generate_response(self, request: ResponseGenerationRequest) -> GeneratedResponse:
        """Generate response text without deciding whether the system is allowed to send it."""
