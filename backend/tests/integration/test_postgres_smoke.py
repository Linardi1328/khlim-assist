import os
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from alembic.config import Config
from app.config.settings import get_settings
from app.db.models.conversation import Conversation
from app.db.models.event import Event
from app.db.models.handoff import HandoffCase
from app.db.session import normalize_async_database_url
from app.schemas.enums import (
    ChannelName,
    EventStatus,
    HandoffPriority,
    HandoffStatus,
    PICRole,
    ReasonCode,
)
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alembic import command

POSTGRES_SMOKE_DATABASE_URL = "POSTGRES_SMOKE_DATABASE_URL"


@pytest.fixture
def postgres_database_url(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    database_url = os.getenv(POSTGRES_SMOKE_DATABASE_URL)
    if not database_url:
        pytest.skip(f"{POSTGRES_SMOKE_DATABASE_URL} is not set")

    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    config = Config("alembic.ini")
    command.upgrade(config, "head")

    yield database_url

    get_settings.cache_clear()


@pytest.fixture
async def postgres_session(postgres_database_url: str) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(normalize_async_database_url(postgres_database_url))
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_connection_and_alembic_upgrade(
    postgres_session: AsyncSession,
) -> None:
    result = await postgres_session.execute(text("SELECT 1"))

    assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_postgres_event_persistence(postgres_session: AsyncSession) -> None:
    slug = f"postgres-smoke-event-{uuid4().hex}"
    event = Event(
        slug=slug,
        name="PostgreSQL Smoke Event",
        status=EventStatus.PUBLISHED,
        venue="Synthetic Venue",
        start_date=date(2027, 7, 10),
        end_date=date(2027, 7, 11),
        registration_open=True,
        registration_deadline=datetime(2027, 6, 30, 23, 59, tzinfo=UTC),
        registration_url="https://example.com/postgres-smoke",
        is_active=True,
    )
    postgres_session.add(event)
    await postgres_session.commit()

    fetched = await postgres_session.scalar(select(Event).where(Event.slug == slug))

    assert fetched is not None
    assert fetched.name == "PostgreSQL Smoke Event"
    assert fetched.is_active is True


@pytest.mark.asyncio
async def test_postgres_handoff_persistence(postgres_session: AsyncSession) -> None:
    event = Event(
        slug=f"postgres-handoff-event-{uuid4().hex}",
        name="PostgreSQL Handoff Event",
        status=EventStatus.PUBLISHED,
    )
    postgres_session.add(event)
    await postgres_session.flush()

    conversation = Conversation(
        channel=ChannelName.WHATSAPP,
        external_user_ref=f"anon_postgres_user_{uuid4().hex}",
        event_id=event.id,
    )
    postgres_session.add(conversation)
    await postgres_session.flush()

    handoff = HandoffCase(
        conversation_id=conversation.id,
        event_id=event.id,
        reason_code=ReasonCode.PAYMENT_VERIFICATION,
        category="PAYMENT",
        summary="Synthetic PostgreSQL payment lookup request.",
        assigned_pic_role=PICRole.FINANCE,
        priority=HandoffPriority.NORMAL,
        status=HandoffStatus.OPEN,
    )
    postgres_session.add(handoff)
    await postgres_session.commit()

    fetched = await postgres_session.scalar(select(HandoffCase).where(HandoffCase.id == handoff.id))

    assert fetched is not None
    assert fetched.assigned_pic_role == PICRole.FINANCE
