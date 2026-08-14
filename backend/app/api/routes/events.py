from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.event import Event
from app.db.session import get_db_session
from app.schemas.events import EventRead

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[EventRead])
async def list_events(session: AsyncSession = Depends(get_db_session)) -> list[Event]:
    result = await session.scalars(select(Event).order_by(Event.start_date, Event.name))
    return list(result)


@router.get("/{event_id}", response_model=EventRead)
async def get_event(event_id: UUID, session: AsyncSession = Depends(get_db_session)) -> Event:
    event = await session.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event
