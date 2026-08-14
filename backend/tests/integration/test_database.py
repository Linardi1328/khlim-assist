from datetime import UTC, date, datetime

import pytest
from app.db.models.conversation import Conversation
from app.db.models.event import Event
from app.db.models.handoff import HandoffCase
from app.schemas.enums import (
    ChannelName,
    EventStatus,
    HandoffPriority,
    HandoffStatus,
    PICRole,
    ReasonCode,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_database_session_behavior(db_session: AsyncSession) -> None:
    result = await db_session.execute(select(1))

    assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_basic_event_persistence(db_session: AsyncSession) -> None:
    event = Event(
        slug="sample-persisted-event",
        name="Sample Persisted Event",
        status=EventStatus.PUBLISHED,
        venue="Sample Venue",
        start_date=date(2027, 6, 12),
        end_date=date(2027, 6, 13),
        registration_open=True,
        registration_deadline=datetime(2027, 5, 31, 23, 59, tzinfo=UTC),
        registration_url="https://example.com/register",
        is_active=True,
    )
    db_session.add(event)
    await db_session.commit()

    fetched = await db_session.scalar(select(Event).where(Event.slug == "sample-persisted-event"))

    assert fetched is not None
    assert fetched.name == "Sample Persisted Event"
    assert fetched.is_active is True


@pytest.mark.asyncio
async def test_handoff_persistence(db_session: AsyncSession) -> None:
    event = Event(slug="handoff-event", name="Handoff Event", status=EventStatus.PUBLISHED)
    db_session.add(event)
    await db_session.flush()

    conversation = Conversation(
        channel=ChannelName.WHATSAPP,
        external_user_ref="anon_user",
        event_id=event.id,
    )
    db_session.add(conversation)
    await db_session.flush()

    handoff = HandoffCase(
        conversation_id=conversation.id,
        event_id=event.id,
        reason_code=ReasonCode.PAYMENT_VERIFICATION,
        category="PAYMENT",
        summary="Synthetic payment lookup request.",
        assigned_pic_role=PICRole.FINANCE,
        priority=HandoffPriority.NORMAL,
        status=HandoffStatus.OPEN,
    )
    db_session.add(handoff)
    await db_session.commit()

    fetched = await db_session.scalar(
        select(HandoffCase).where(HandoffCase.reason_code == ReasonCode.PAYMENT_VERIFICATION)
    )

    assert fetched is not None
    assert fetched.assigned_pic_role == PICRole.FINANCE
