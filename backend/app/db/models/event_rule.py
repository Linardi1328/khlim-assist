from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Date, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.common import JsonObject, JSONType, TimestampMixin
from app.schemas.enums import RuleStatus

if TYPE_CHECKING:
    from app.db.models.event import Event


class EventRule(TimestampMixin, Base):
    __tablename__ = "event_rules"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    rule_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    value: Mapped[JsonObject] = mapped_column(JSONType, nullable=False)
    status: Mapped[RuleStatus] = mapped_column(
        String(40),
        default=RuleStatus.ACTIVE,
        nullable=False,
    )
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_until: Mapped[date | None] = mapped_column(Date, nullable=True)

    event: Mapped["Event"] = relationship("Event", back_populates="rules")
