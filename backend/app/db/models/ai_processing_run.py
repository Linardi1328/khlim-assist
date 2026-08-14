from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.common import CreatedAtMixin, JsonObject, JSONType
from app.schemas.enums import AIProcessingStatus, DecisionLevel, LanguageCode, LanguageMode, PICRole

if TYPE_CHECKING:
    from app.db.models.conversation import Conversation
    from app.db.models.event import Event
    from app.db.models.message import Message


class AIProcessingRun(CreatedAtMixin, Base):
    __tablename__ = "ai_processing_runs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    message_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str | None] = mapped_column(String(160), nullable=True)

    primary_language: Mapped[LanguageCode | None] = mapped_column(String(20), nullable=True)
    language_mode: Mapped[LanguageMode | None] = mapped_column(String(20), nullable=True)
    interpreted_intents: Mapped[list[JsonObject]] = mapped_column(JSONType, default=list)

    decision_level: Mapped[DecisionLevel | None] = mapped_column(String(20), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    knowledge_found: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    knowledge_source: Mapped[str | None] = mapped_column(String(240), nullable=True)
    requires_clarification: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recommended_pic_role: Mapped[PICRole | None] = mapped_column(String(80), nullable=True)

    draft_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_status: Mapped[AIProcessingStatus] = mapped_column(
        String(40),
        default=AIProcessingStatus.PENDING,
        nullable=False,
        index=True,
    )

    provider_request_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    message: Mapped["Message"] = relationship("Message", back_populates="ai_processing_runs")
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="ai_processing_runs",
    )
    event: Mapped["Event | None"] = relationship("Event", back_populates="ai_processing_runs")
