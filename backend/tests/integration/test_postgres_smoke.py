import os
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from alembic.config import Config
from app.ai.fake import FakeAIProvider
from app.config.settings import get_settings
from app.db.models.ai_processing_run import AIProcessingRun
from app.db.models.conversation import Conversation
from app.db.models.event import Event
from app.db.models.event_rule import EventRule
from app.db.models.handoff import HandoffCase
from app.db.models.message import Message
from app.db.session import normalize_async_database_url
from app.messaging.base import IncomingMessage
from app.messaging.whatsapp import WhatsAppStatusNotification
from app.messaging.whatsapp_client import WhatsAppSendResponse
from app.schemas.enums import (
    ChannelName,
    ContentType,
    DecisionLevel,
    EventStatus,
    HandoffPriority,
    HandoffStatus,
    MessageDeliveryStatus,
    MessageDirection,
    PICRole,
    ReasonCode,
    RuleStatus,
    SenderType,
)
from app.services.ai_processing import AIProcessingService
from app.services.whatsapp_ingestion import WhatsAppWebhookProcessor
from app.services.whatsapp_outbound import WhatsAppOutboundService
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


async def test_postgres_phase_1_inbound_duplicate_idempotency(
    postgres_session: AsyncSession,
) -> None:
    external_message_id = f"wamid.synthetic_pg_inbound_{uuid4().hex}"
    incoming = IncomingMessage(
        channel=ChannelName.WHATSAPP,
        external_user_ref=f"anon_pg_user_{uuid4().hex}",
        external_message_id=external_message_id,
        content_type=ContentType.TEXT,
        text="KHLIM Assist Phase 1 inbound test",
        metadata={"provider": "meta_whatsapp", "timestamp": "1700000000"},
    )
    processor = WhatsAppWebhookProcessor()

    first = await processor.process(postgres_session, [incoming], [])
    second = await processor.process(postgres_session, [incoming], [])

    rows = list(
        await postgres_session.scalars(
            select(Message).where(Message.external_message_id == external_message_id)
        )
    )
    assert first.messages_persisted == 1
    assert second.duplicates_ignored == 1
    assert len(rows) == 1


class FakePostgresWhatsAppClient:
    async def send_text_message(self, to: str, text: str) -> WhatsAppSendResponse:
        return WhatsAppSendResponse(
            provider_message_id=f"wamid.synthetic_pg_outbound_{uuid4().hex}"
        )

    async def send_template_message(
        self,
        to: str,
        template_name: str,
        language_code: str,
    ) -> WhatsAppSendResponse:
        return WhatsAppSendResponse(
            provider_message_id=f"wamid.synthetic_pg_template_{uuid4().hex}"
        )


async def test_postgres_phase_1_outbound_and_status_persistence(
    postgres_session: AsyncSession,
) -> None:
    service = WhatsAppOutboundService(client=FakePostgresWhatsAppClient())  # type: ignore[arg-type]

    message = await service.send_text(postgres_session, "15550000001", "Synthetic outbound")
    processor = WhatsAppWebhookProcessor()
    await processor.process(
        postgres_session,
        [],
        [
            WhatsAppStatusNotification(
                external_message_id=message.external_message_id or "",
                status="delivered",
            )
        ],
    )

    fetched = await postgres_session.scalar(select(Message).where(Message.id == message.id))
    assert fetched is not None
    assert fetched.direction == MessageDirection.OUTBOUND
    assert fetched.delivery_status == MessageDeliveryStatus.DELIVERED


async def test_postgres_phase_2_ai_processing_persistence(
    postgres_session: AsyncSession,
) -> None:
    event = Event(
        slug=f"postgres-ai-event-{uuid4().hex}",
        name="PostgreSQL AI Event",
        status=EventStatus.PUBLISHED,
        registration_open=True,
        registration_url="https://example.com/postgres-ai",
        is_active=True,
    )
    postgres_session.add(event)
    await postgres_session.flush()
    postgres_session.add(
        EventRule(
            event_id=event.id,
            category="U16",
            rule_type="registration_fee",
            value={"amount_myr": 180},
            status=RuleStatus.ACTIVE,
        )
    )
    conversation = Conversation(
        channel=ChannelName.WHATSAPP,
        external_user_ref=f"anon_pg_ai_user_{uuid4().hex}",
        event_id=event.id,
    )
    postgres_session.add(conversation)
    await postgres_session.flush()
    message = Message(
        conversation_id=conversation.id,
        external_message_id=f"wamid.synthetic_pg_ai_{uuid4().hex}",
        direction=MessageDirection.INBOUND,
        sender_type=SenderType.PARTICIPANT,
        content_type=ContentType.TEXT,
        text_content="How much is U16?",
    )
    postgres_session.add(message)
    await postgres_session.commit()

    run = await AIProcessingService(
        provider=FakeAIProvider(),
        settings=get_settings().model_copy(update={"ai_processing_enabled": True}),
    ).process_message(postgres_session, message.id)

    fetched = await postgres_session.scalar(
        select(AIProcessingRun).where(AIProcessingRun.id == run.id)
    )
    assert fetched is not None
    assert fetched.message_id == message.id
    assert fetched.conversation_id == conversation.id
    assert fetched.interpreted_intents[0]["type"] == "fee"
    assert fetched.decision_level == DecisionLevel.GREEN
    assert fetched.draft_response is not None
