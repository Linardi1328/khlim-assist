import argparse
import asyncio

from sqlalchemy import desc, select

from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.db.session import AsyncSessionLocal
from app.schemas.enums import ChannelName


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show recent stored WhatsApp messages.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum rows to display")
    return parser.parse_args()


async def run() -> int:
    args = parse_args()
    limit = max(1, min(args.limit, 50))
    async with AsyncSessionLocal() as session:
        rows = await session.execute(
            select(Message, Conversation)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(Conversation.channel == ChannelName.WHATSAPP)
            .order_by(desc(Message.created_at))
            .limit(limit)
        )

    for message, conversation in rows:
        text = message.text_content or ""
        if len(text) > 120:
            text = f"{text[:117]}..."
        print(
            " | ".join(
                [
                    str(message.created_at),
                    message.direction.value,
                    str(message.delivery_status.value if message.delivery_status else "-"),
                    conversation.external_user_ref,
                    str(message.external_message_id or "-"),
                    text,
                ]
            )
        )
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(run()))


if __name__ == "__main__":
    main()
