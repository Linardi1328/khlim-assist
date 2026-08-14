from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field

from app.config.settings import Settings, get_settings
from app.messaging.base import IncomingMessage, OutgoingMessage, SendMessageResult
from app.messaging.meta_errors import MetaWhatsAppError
from app.messaging.whatsapp_client import WhatsAppCloudClient
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


def _error_code_or_none(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return None


class WhatsAppStatusNotification(BaseModel):
    external_message_id: str
    status: str
    phone_number_id: str | None = None
    timestamp: str | None = None
    recipient_id: str | None = None
    provider_error_code: str | None = None
    provider_error_message: str | None = Field(default=None, max_length=500)


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


def normalize_whatsapp_status_payload(
    payload: Mapping[str, Any],
) -> list[WhatsAppStatusNotification]:
    normalized: list[WhatsAppStatusNotification] = []
    for entry in _as_sequence(payload.get("entry")):
        entry_map = _as_mapping(entry)
        for change in _as_sequence(entry_map.get("changes")):
            change_map = _as_mapping(change)
            value = _as_mapping(change_map.get("value"))
            metadata = _as_mapping(value.get("metadata"))
            phone_number_id = _string_or_none(metadata.get("phone_number_id"))

            for status_item in _as_sequence(value.get("statuses")):
                status_map = _as_mapping(status_item)
                message_id = _string_or_none(status_map.get("id"))
                status = _string_or_none(status_map.get("status"))
                if not message_id or not status:
                    continue

                error_code: str | None = None
                error_message: str | None = None
                errors = _as_sequence(status_map.get("errors"))
                if errors:
                    first_error = _as_mapping(errors[0])
                    error_code = _error_code_or_none(first_error.get("code"))
                    error_message = (
                        _string_or_none(first_error.get("title"))
                        or _string_or_none(first_error.get("message"))
                        or _string_or_none(first_error.get("error_data"))
                    )

                normalized.append(
                    WhatsAppStatusNotification(
                        external_message_id=message_id,
                        status=status,
                        phone_number_id=phone_number_id,
                        timestamp=_string_or_none(status_map.get("timestamp")),
                        recipient_id=_string_or_none(status_map.get("recipient_id")),
                        provider_error_code=error_code,
                        provider_error_message=error_message,
                    )
                )
    return normalized


class WhatsAppChannel:
    """Phase 0 WhatsApp channel adapter.

    Inbound parsing is implemented. Outbound sending is guarded by Phase 1 sandbox settings.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def receive_message(self, payload: object) -> list[IncomingMessage]:
        return normalize_whatsapp_webhook_payload(_as_mapping(payload))

    async def send_message(self, message: OutgoingMessage) -> SendMessageResult:
        client = WhatsAppCloudClient(self.settings)
        try:
            response = await client.send_text_message(message.external_user_ref, message.text)
        except MetaWhatsAppError as exc:
            return SendMessageResult(sent=False, error=type(exc).__name__)
        return SendMessageResult(sent=True, provider_message_id=response.provider_message_id)
