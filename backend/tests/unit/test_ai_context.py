from datetime import UTC, datetime, timedelta

from app.ai.context import ConversationContextBuilder
from app.config.settings import Settings
from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.schemas.enums import ChannelName, ContentType, MessageDirection, SenderType
from sqlalchemy.ext.asyncio import AsyncSession


async def test_context_builder_orders_recent_text_messages(db_session: AsyncSession) -> None:
    conversation = Conversation(channel=ChannelName.WHATSAPP, external_user_ref="15550000001")
    db_session.add(conversation)
    await db_session.flush()
    base_time = datetime(2027, 1, 1, tzinfo=UTC)

    for index in range(12):
        db_session.add(
            Message(
                conversation_id=conversation.id,
                direction=MessageDirection.INBOUND,
                sender_type=SenderType.PARTICIPANT if index % 2 == 0 else SenderType.HUMAN,
                content_type=ContentType.TEXT,
                text_content=f"message {index}",
                created_at=base_time + timedelta(minutes=index),
            )
        )
    db_session.add(
        Message(
            conversation_id=conversation.id,
            direction=MessageDirection.INBOUND,
            sender_type=SenderType.PARTICIPANT,
            content_type=ContentType.IMAGE,
            text_content=None,
        )
    )
    await db_session.commit()

    context = await ConversationContextBuilder(Settings(ai_context_message_limit=3)).build(
        db_session,
        conversation.id,
    )

    assert [message.text for message in context.messages] == [
        "message 9",
        "message 10",
        "message 11",
    ]
    assert [message.role for message in context.messages] == ["khlim", "participant", "khlim"]
