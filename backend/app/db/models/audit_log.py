from uuid import UUID, uuid4

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import CreatedAtMixin, JsonObject, JSONType
from app.schemas.enums import AuditActorType


class AuditLog(CreatedAtMixin, Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    actor_type: Mapped[AuditActorType] = mapped_column(String(40), nullable=False)
    actor_ref: Mapped[str | None] = mapped_column(String(160), nullable=True)
    metadata_json: Mapped[JsonObject] = mapped_column(
        "metadata",
        JSONType,
        default=dict,
        nullable=False,
    )
