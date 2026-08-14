from collections.abc import Mapping, Sequence
from typing import Any

from app.config.settings import Settings, get_settings
from app.messaging.base import IncomingMessage, OutgoingMessage, SendMessageResult
from app.schemas.enums import ChannelName, ContentType


def _as_mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _as_sequence(value: object) -> Sequence[object]:
    if isinstance(value, list):
        return value
    return ()


def _string_or_none(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def normalize_whatsapp_webhook_payload(payload: Mapping[str, Any]) -> list[IncomingMessage]:
    """Extract supported WhatsApp text messages from a Meta webhook payload.

    Unsupported changes, statuses, non-text messages, and malformed structures are ignored.
    """

    normalized: list[IncomingMessage] = []
    for entry in _as_sequence(payload.get("entry")):
        entry_map = _as_mapping(entry)
        for change in _as_sequence(entry_map.get("changes")):
            change_map = _as_mapping(change)
            value = _as_mapping(change_map.get("value"))
            metadata = _as_mapping(value.get("metadata"))
            phone_number_id = _string_or_none(metadata.get("phone_number_id"))

            for message in _as_sequence(value.get("messages")):
                message_map = _as_mapping(message)
                if message_map.get("type") != "text":
                    continue
                text = _as_mapping(message_map.get("text"))
                body = _string_or_none(text.get("body"))
                sender = _string_or_none(message_map.get("from"))
                if not body or not sender:
                    continue

                normalized.append(
                    IncomingMessage(
                        channel=ChannelName.WHATSAPP,
                        external_user_ref=sender,
                        external_message_id=_string_or_none(message_map.get("id")),
                        content_type=ContentType.TEXT,
                        text=body,
                        metadata={
                            "provider": "meta_whatsapp",
                            "phone_number_id": phone_number_id,
                            "timestamp": _string_or_none(message_map.get("timestamp")),
                        },
                    )
                )
    return normalized


class WhatsAppChannel:
    """Phase 0 WhatsApp channel adapter.

    Inbound parsing is implemented. Outbound sending is intentionally disabled until a later
    sandbox/integration phase.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def receive_message(self, payload: object) -> list[IncomingMessage]:
        return normalize_whatsapp_webhook_payload(_as_mapping(payload))

    async def send_message(self, message: OutgoingMessage) -> SendMessageResult:
        return SendMessageResult(
            sent=False,
            error="WhatsApp sending is disabled in KHLIM Assist v0.1 Phase 0.",
        )
