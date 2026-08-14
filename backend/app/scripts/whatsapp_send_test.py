import argparse
import asyncio

from app.db.session import AsyncSessionLocal
from app.messaging.meta_errors import (
    MetaWhatsAppError,
    OutboundMessagingDisabled,
    SandboxRecipientNotAllowed,
)
from app.services.whatsapp_outbound import WhatsAppOutboundService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a controlled WhatsApp sandbox test message.")
    parser.add_argument("--to", required=True, help="Allowlisted sandbox recipient phone number")
    message_mode = parser.add_mutually_exclusive_group(required=True)
    message_mode.add_argument("--text", help="Text message body to send")
    message_mode.add_argument("--template", help="Template name to send")
    parser.add_argument("--language", default="en_US", help="Template language code")
    return parser.parse_args()


async def run() -> int:
    args = parse_args()
    service = WhatsAppOutboundService()
    try:
        async with AsyncSessionLocal() as session:
            if args.text:
                message = await service.send_text(session, args.to, args.text)
            else:
                message = await service.send_template(
                    session,
                    args.to,
                    args.template,
                    args.language,
                )
    except (OutboundMessagingDisabled, SandboxRecipientNotAllowed) as exc:
        print(f"BLOCKED LOCALLY: {exc}")
        return 1
    except MetaWhatsAppError as exc:
        print(f"FAILED: {exc}")
        return 1

    print(f"ACCEPTED provider_message_id={message.external_message_id}")
    print(f"stored_message_id={message.id}")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(run()))


if __name__ == "__main__":
    main()
