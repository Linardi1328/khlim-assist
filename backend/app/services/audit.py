from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog
from app.schemas.enums import AuditActorType


async def record_audit_event(
    session: AsyncSession,
    event_type: str,
    entity_type: str,
    entity_id: str,
    metadata: dict[str, Any] | None = None,
    actor_type: AuditActorType = AuditActorType.SYSTEM,
    actor_ref: str | None = None,
) -> None:
    session.add(
        AuditLog(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_type=actor_type,
            actor_ref=actor_ref,
            metadata_json=metadata or {},
        )
    )
    await session.flush()
