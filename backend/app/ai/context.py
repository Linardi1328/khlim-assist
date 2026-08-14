from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings, get_settings
from app.db.models.message import Message
from app.schemas.enums import ContentType, SenderType
from app.schemas.interpretation import InterpretationContextMessage


class ConversationContext(BaseModel):
    conversation_id: UUID
    messages: list[InterpretationContextMessage] = Field(default_factory=list)

    def as_lines(self) -> list[str]:
        return [f"{message.role}: {message.text}" for message in self.messages]


class ConversationContextBuilder:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def build(self, session: AsyncSession, conversation_id: UUID) -> ConversationContext:
        limit = max(1, self.settings.ai_context_message_limit)
        rows = list(
            await session.scalars(
                select(Message)
                .where(
                    Message.conversation_id == conversation_id,
                    Message.content_type == ContentType.TEXT,
                    Message.text_content.is_not(None),
                )
                .order_by(Message.created_at.desc())
                .limit(limit)
            )
        )
        messages = [
            InterpretationContextMessage(
                role=_context_role(message.sender_type),
                text=message.text_content or "",
            )
            for message in reversed(rows)
            if message.text_content
        ]
        return ConversationContext(conversation_id=conversation_id, messages=messages)


def _context_role(sender_type: SenderType) -> str:
    if sender_type == SenderType.PARTICIPANT:
        return "participant"
    if sender_type in {SenderType.HUMAN, SenderType.AI}:
        return "khlim"
    return "system"
