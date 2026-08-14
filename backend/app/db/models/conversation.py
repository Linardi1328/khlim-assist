from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.common import TimestampMixin
from app.schemas.enums import ChannelName, ConversationState, LanguageCode

if TYPE_CHECKING:
    from app.db.models.event import Event
    from app.db.models.handoff import HandoffCase
    from app.db.models.message import Message


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    channel: Mapped[ChannelName] = mapped_column(String(40), nullable=False, index=True)
    external_user_ref: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    event_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    preferred_language: Mapped[LanguageCode | None] = mapped_column(String(20), nullable=True)
    state: Mapped[ConversationState] = mapped_column(
        String(60),
        default=ConversationState.AI_ACTIVE,
        nullable=False,
        index=True,
    )
    assigned_pic_role: Mapped[str | None] = mapped_column(String(80), nullable=True)
    human_takeover: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    event: Mapped["Event | None"] = relationship("Event", back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="conversation")
    handoffs: Mapped[list["HandoffCase"]] = relationship(
        "HandoffCase",
        back_populates="conversation",
    )
