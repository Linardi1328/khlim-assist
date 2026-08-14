from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.common import TimestampMixin
from app.schemas.enums import EventStatus

if TYPE_CHECKING:
    from app.db.models.conversation import Conversation
    from app.db.models.event_rule import EventRule
    from app.db.models.faq_entry import FAQEntry
    from app.db.models.handoff import HandoffCase


class Event(TimestampMixin, Base):
    __tablename__ = "events"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[EventStatus] = mapped_column(
        String(40),
        default=EventStatus.DRAFT,
        nullable=False,
    )
    venue: Mapped[str | None] = mapped_column(String(240), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    registration_open: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    registration_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    registration_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)

    faq_entries: Mapped[list["FAQEntry"]] = relationship("FAQEntry", back_populates="event")
    rules: Mapped[list["EventRule"]] = relationship("EventRule", back_populates="event")
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="event",
    )
    handoffs: Mapped[list["HandoffCase"]] = relationship(
        "HandoffCase",
        back_populates="event",
    )
