from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.common import CreatedAtMixin
from app.schemas.enums import AnswerSource, FAQCategory, FAQStatus

if TYPE_CHECKING:
    from app.db.models.event import Event


class FAQEntry(CreatedAtMixin, Base):
    __tablename__ = "faq_entries"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    event_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    faq_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    category: Mapped[FAQCategory] = mapped_column(String(60), nullable=False, index=True)
    generalized_question: Mapped[str] = mapped_column(Text, nullable=False)
    answer_source: Mapped[AnswerSource] = mapped_column(String(80), nullable=False)
    static_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_reply_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_lookup: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_human: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[FAQStatus] = mapped_column(String(40), default=FAQStatus.DRAFT, nullable=False)
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_updated_by: Mapped[str | None] = mapped_column(String(120), nullable=True)

    event: Mapped["Event | None"] = relationship("Event", back_populates="faq_entries")
