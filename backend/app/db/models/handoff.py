from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.common import CreatedAtMixin
from app.schemas.enums import HandoffPriority, HandoffStatus, ReasonCode

if TYPE_CHECKING:
    from app.db.models.conversation import Conversation
    from app.db.models.event import Event


class HandoffCase(CreatedAtMixin, Base):
    __tablename__ = "handoff_cases"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
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
    reason_code: Mapped[ReasonCode] = mapped_column(String(80), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_pic_role: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    priority: Mapped[HandoffPriority] = mapped_column(
        String(40),
        default=HandoffPriority.NORMAL,
        nullable=False,
    )
    status: Mapped[HandoffStatus] = mapped_column(
        String(40),
        default=HandoffStatus.OPEN,
        nullable=False,
        index=True,
    )
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="handoffs",
    )
    event: Mapped["Event | None"] = relationship("Event", back_populates="handoffs")
