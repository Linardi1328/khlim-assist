from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.handoff import HandoffCase
from app.db.session import get_db_session
from app.schemas.handoffs import HandoffCaseRead

router = APIRouter(prefix="/handoffs", tags=["handoffs"])


@router.get("", response_model=list[HandoffCaseRead])
async def list_handoffs(session: AsyncSession = Depends(get_db_session)) -> list[HandoffCase]:
    result = await session.scalars(select(HandoffCase).order_by(HandoffCase.created_at.desc()))
    return list(result)


@router.get("/{handoff_id}", response_model=HandoffCaseRead)
async def get_handoff(
    handoff_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> HandoffCase:
    handoff = await session.get(HandoffCase, handoff_id)
    if handoff is None:
        raise HTTPException(status_code=404, detail="Handoff case not found")
    return handoff
