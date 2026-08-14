from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.common import CreatedAtMixin
from app.schemas.enums import ContentType, LanguageCode, MessageDirection, SenderType

if TYPE_CHECKING:
    from app.db.models.conversation import Conversation


class Message(CreatedAtMixin, Base):
    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_message_id: Mapped[str | None] = mapped_column(String(240), nullable=True, index=True)
    direction: Mapped[MessageDirection] = mapped_column(String(40), nullable=False)
    sender_type: Mapped[SenderType] = mapped_column(String(40), nullable=False)
    language: Mapped[LanguageCode | None] = mapped_column(String(20), nullable=True)
    content_type: Mapped[ContentType] = mapped_column(
        String(40),
        default=ContentType.TEXT,
        nullable=False,
    )
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
