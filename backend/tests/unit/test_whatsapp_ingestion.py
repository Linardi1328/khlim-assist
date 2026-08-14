from datetime import UTC, datetime

from app.config.settings import Settings
from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.messaging.base import IncomingMessage
from app.messaging.whatsapp import WhatsAppStatusNotification
from app.schemas.enums import (
    ChannelName,
    ContentType,
    MessageDeliveryStatus,
    MessageDirection,
    SenderType,
)
from app.services.whatsapp_ingestion import WhatsAppWebhookProcessor
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def meta_datetime(epoch_seconds: int) -> datetime:
    return datetime.fromtimestamp(epoch_seconds, tz=UTC)


def assert_meta_epoch(value: datetime | None, epoch_seconds: int) -> None:
    assert value is not None
    normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    assert normalized == meta_datetime(epoch_seconds)


def incoming(
    message_id: str | None = "wamid.synthetic_inbound_1",
    text: str = "KHLIM Assist Phase 1 inbound test",
    sender: str = "anon_whatsapp_user_1",
    phone_number_id: str = "phone-number-1",
) -> IncomingMessage:
    return IncomingMessage(
        channel=ChannelName.WHATSAPP,
        external_user_ref=sender,
        external_message_id=message_id,
        content_type=ContentType.TEXT,
        text=text,
        metadata={
            "provider": "meta_whatsapp",
            "phone_number_id": phone_number_id,
            "timestamp": "1700000000",
        },
    )


async def message_count(session: AsyncSession) -> int:
    return len(list(await session.scalars(select(Message))))


async def conversation_count(session: AsyncSession) -> int:
    return len(list(await session.scalars(select(Conversation))))


async def test_inbound_text_message_persists(db_session: AsyncSession) -> None:
    processor = WhatsAppWebhookProcessor(Settings(meta_phone_number_id="phone-number-1"))

    result = await processor.process(db_session, [incoming()], [])

    assert result.messages_persisted == 1
    assert await conversation_count(db_session) == 1
    assert await message_count(db_session) == 1


async def test_mixed_language_text_persists(db_session: AsyncSession) -> None:
    processor = WhatsAppWebhookProcessor(Settings(meta_phone_number_id="phone-number-1"))

    result = await processor.process(
        db_session,
        [incoming(message_id="wamid.synthetic_mixed_1", text="coach 2012 可以打 u16 吗")],
        [],
    )

    assert result.messages_persisted == 1
    stored = await db_session.scalar(select(Message))
    assert stored is not None
    assert stored.text_content == "coach 2012 可以打 u16 吗"


async def test_multiple_text_messages_in_one_webhook_persist(db_session: AsyncSession) -> None:
    processor = WhatsAppWebhookProcessor(Settings(meta_phone_number_id="phone-number-1"))

    result = await processor.process(
        db_session,
        [
            incoming(message_id="wamid.synthetic_multi_1", sender="anon_user_1"),
            incoming(message_id="wamid.synthetic_multi_2", sender="anon_user_2"),
        ],
        [],
    )

    assert result.messages_persisted == 2
    assert await conversation_count(db_session) == 2
    assert await message_count(db_session) == 2


async def test_missing_message_id_persists_but_cannot_dedupe(db_session: AsyncSession) -> None:
    processor = WhatsAppWebhookProcessor(Settings(meta_phone_number_id="phone-number-1"))

    result = await processor.process(db_session, [incoming(message_id=None)], [])

    assert result.messages_persisted == 1
    assert await message_count(db_session) == 1


async def test_wrong_phone_number_id_is_ignored(db_session: AsyncSession) -> None:
    processor = WhatsAppWebhookProcessor(Settings(meta_phone_number_id="expected-phone-id"))

    result = await processor.process(db_session, [incoming(phone_number_id="other-phone-id")], [])

    assert result.ignored_events == 1
    assert result.messages_persisted == 0
    assert await conversation_count(db_session) == 0
    assert await message_count(db_session) == 0


async def test_duplicate_inbound_webhook_does_not_create_second_message(
    db_session: AsyncSession,
) -> None:
    processor = WhatsAppWebhookProcessor(Settings(meta_phone_number_id="phone-number-1"))
    payload = [incoming()]

    first = await processor.process(db_session, payload, [])
    second = await processor.process(db_session, payload, [])

    assert first.messages_persisted == 1
    assert second.duplicates_ignored == 1
    assert await conversation_count(db_session) == 1
    assert await message_count(db_session) == 1


async def test_duplicate_database_constraint_path_is_idempotent(
    db_session: AsyncSession,
) -> None:
    processor = WhatsAppWebhookProcessor(Settings(meta_phone_number_id="phone-number-1"))
    await processor.process(db_session, [incoming()], [])

    duplicate = incoming(sender="another_anon_user")
    result = await processor.process(db_session, [duplicate], [])

    assert result.duplicates_ignored == 1
    assert await message_count(db_session) == 1


async def create_outbound_message(
    db_session: AsyncSession,
    status: MessageDeliveryStatus = MessageDeliveryStatus.ACCEPTED,
    updated_at: datetime | None = None,
) -> Message:
    conversation = Conversation(
        channel=ChannelName.WHATSAPP,
        external_user_ref="15550000001",
    )
    db_session.add(conversation)
    await db_session.flush()
    message = Message(
        conversation_id=conversation.id,
        external_message_id="wamid.synthetic_outbound_status_1",
        direction=MessageDirection.OUTBOUND,
        sender_type=SenderType.SYSTEM,
        content_type=ContentType.TEXT,
        text_content="Synthetic outbound",
        delivery_status=status,
        delivery_status_updated_at=updated_at,
    )
    db_session.add(message)
    await db_session.commit()
    return message


async def test_delivery_status_progression_to_read(db_session: AsyncSession) -> None:
    message = await create_outbound_message(db_session)
    processor = WhatsAppWebhookProcessor()

    for status, timestamp in [
        ("sent", "1700000010"),
        ("delivered", "1700000020"),
        ("read", "1700000030"),
    ]:
        await processor.process(
            db_session,
            [],
            [
                WhatsAppStatusNotification(
                    external_message_id="wamid.synthetic_outbound_status_1",
                    status=status,
                    timestamp=timestamp,
                    phone_number_id=None,
                )
            ],
        )

    await db_session.refresh(message)
    assert message.delivery_status == MessageDeliveryStatus.READ
    assert_meta_epoch(message.delivery_status_updated_at, 1700000030)


async def test_delivery_status_failed_from_accepted(db_session: AsyncSession) -> None:
    message = await create_outbound_message(db_session)
    processor = WhatsAppWebhookProcessor()

    await processor.process(
        db_session,
        [],
        [
            WhatsAppStatusNotification(
                external_message_id="wamid.synthetic_outbound_status_1",
                status="failed",
                timestamp="1700000010",
                provider_error_code="synthetic_error",
                provider_error_message="Synthetic provider error",
            )
        ],
    )

    await db_session.refresh(message)
    assert message.delivery_status == MessageDeliveryStatus.FAILED
    assert_meta_epoch(message.delivery_status_updated_at, 1700000010)
    assert message.provider_error_code == "synthetic_error"
    assert message.provider_error_message == "Synthetic provider error"


async def test_read_does_not_regress_to_older_delivered(db_session: AsyncSession) -> None:
    message = await create_outbound_message(
        db_session,
        status=MessageDeliveryStatus.READ,
        updated_at=meta_datetime(1700000030),
    )
    processor = WhatsAppWebhookProcessor()

    result = await processor.process(
        db_session,
        [],
        [
            WhatsAppStatusNotification(
                external_message_id=message.external_message_id or "",
                status="delivered",
                timestamp="1700000020",
            )
        ],
    )

    await db_session.refresh(message)
    assert result.statuses_updated == 0
    assert message.delivery_status == MessageDeliveryStatus.READ
    assert_meta_epoch(message.delivery_status_updated_at, 1700000030)


async def test_delivered_does_not_regress_to_older_sent(db_session: AsyncSession) -> None:
    message = await create_outbound_message(
        db_session,
        status=MessageDeliveryStatus.DELIVERED,
        updated_at=meta_datetime(1700000020),
    )
    processor = WhatsAppWebhookProcessor()

    result = await processor.process(
        db_session,
        [],
        [
            WhatsAppStatusNotification(
                external_message_id=message.external_message_id or "",
                status="sent",
                timestamp="1700000010",
            )
        ],
    )

    await db_session.refresh(message)
    assert result.statuses_updated == 0
    assert message.delivery_status == MessageDeliveryStatus.DELIVERED
    assert_meta_epoch(message.delivery_status_updated_at, 1700000020)


async def test_duplicate_status_with_older_timestamp_does_not_regress_timestamp(
    db_session: AsyncSession,
) -> None:
    message = await create_outbound_message(
        db_session,
        status=MessageDeliveryStatus.DELIVERED,
        updated_at=meta_datetime(1700000020),
    )
    processor = WhatsAppWebhookProcessor()

    result = await processor.process(
        db_session,
        [],
        [
            WhatsAppStatusNotification(
                external_message_id=message.external_message_id or "",
                status="delivered",
                timestamp="1700000010",
            )
        ],
    )

    await db_session.refresh(message)
    assert result.statuses_updated == 0
    assert message.delivery_status == MessageDeliveryStatus.DELIVERED
    assert_meta_epoch(message.delivery_status_updated_at, 1700000020)


async def test_duplicate_status_with_newer_timestamp_updates_timestamp(
    db_session: AsyncSession,
) -> None:
    message = await create_outbound_message(
        db_session,
        status=MessageDeliveryStatus.DELIVERED,
        updated_at=meta_datetime(1700000020),
    )
    processor = WhatsAppWebhookProcessor()

    result = await processor.process(
        db_session,
        [],
        [
            WhatsAppStatusNotification(
                external_message_id=message.external_message_id or "",
                status="delivered",
                timestamp="1700000030",
            )
        ],
    )

    await db_session.refresh(message)
    assert result.statuses_updated == 1
    assert message.delivery_status == MessageDeliveryStatus.DELIVERED
    assert_meta_epoch(message.delivery_status_updated_at, 1700000030)


async def test_stale_failed_status_does_not_overwrite_read(db_session: AsyncSession) -> None:
    message = await create_outbound_message(
        db_session,
        status=MessageDeliveryStatus.READ,
        updated_at=meta_datetime(1700000030),
    )
    processor = WhatsAppWebhookProcessor()

    result = await processor.process(
        db_session,
        [],
        [
            WhatsAppStatusNotification(
                external_message_id=message.external_message_id or "",
                status="failed",
                timestamp="1700000010",
                provider_error_code="131014",
                provider_error_message="Synthetic failure",
            )
        ],
    )

    await db_session.refresh(message)
    assert result.statuses_updated == 0
    assert message.delivery_status == MessageDeliveryStatus.READ
    assert_meta_epoch(message.delivery_status_updated_at, 1700000030)
    assert message.provider_error_code is None
    assert message.provider_error_message is None


async def test_failed_status_can_recover_to_newer_success(db_session: AsyncSession) -> None:
    message = await create_outbound_message(
        db_session,
        status=MessageDeliveryStatus.FAILED,
        updated_at=meta_datetime(1700000010),
    )
    message.provider_error_code = "131014"
    message.provider_error_message = "Synthetic failure"
    await db_session.commit()
    processor = WhatsAppWebhookProcessor()

    result = await processor.process(
        db_session,
        [],
        [
            WhatsAppStatusNotification(
                external_message_id=message.external_message_id or "",
                status="sent",
                timestamp="1700000020",
            )
        ],
    )

    await db_session.refresh(message)
    assert result.statuses_updated == 1
    assert message.delivery_status == MessageDeliveryStatus.SENT
    assert_meta_epoch(message.delivery_status_updated_at, 1700000020)
    assert message.provider_error_code is None
    assert message.provider_error_message is None


async def test_unknown_status_message_id_is_acknowledged_without_message(
    db_session: AsyncSession,
) -> None:
    processor = WhatsAppWebhookProcessor()

    result = await processor.process(
        db_session,
        [],
        [WhatsAppStatusNotification(external_message_id="wamid.unknown", status="delivered")],
    )

    assert result.statuses_processed == 1
    assert result.statuses_updated == 0
    assert await message_count(db_session) == 0


async def test_repeated_identical_status_is_safe(db_session: AsyncSession) -> None:
    message = await create_outbound_message(db_session)
    processor = WhatsAppWebhookProcessor()
    status = WhatsAppStatusNotification(
        external_message_id=message.external_message_id or "",
        status="delivered",
        timestamp="1700000020",
    )

    await processor.process(db_session, [], [status])
    await processor.process(db_session, [], [status])

    await db_session.refresh(message)
    assert message.delivery_status == MessageDeliveryStatus.DELIVERED
