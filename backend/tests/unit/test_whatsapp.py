import json
from pathlib import Path

import httpx
import pytest
from app.api.webhooks.whatsapp import WhatsAppWebhookPostResponse
from app.config.settings import Settings, get_settings
from app.main import create_app
from app.messaging.base import OutgoingMessage
from app.messaging.whatsapp import WhatsAppChannel, normalize_whatsapp_webhook_payload
from app.schemas.enums import ChannelName, ContentType


def load_fixture(name: str) -> dict[str, object]:
    return json.loads(Path("backend/tests/fixtures", name).read_text(encoding="utf-8"))


def test_whatsapp_payload_normalization_text_message() -> None:
    payload = load_fixture("whatsapp_text_message.json")

    messages = normalize_whatsapp_webhook_payload(payload)

    assert len(messages) == 1
    assert messages[0].channel == ChannelName.WHATSAPP
    assert messages[0].content_type == ContentType.TEXT
    assert messages[0].external_user_ref == "anon_whatsapp_user_001"
    assert messages[0].text == "Where do I register?"


def test_whatsapp_payload_normalization_ignores_unsupported_events() -> None:
    payload = load_fixture("whatsapp_unsupported_event.json")

    assert normalize_whatsapp_webhook_payload(payload) == []


def test_whatsapp_payload_normalization_handles_malformed_payload() -> None:
    assert normalize_whatsapp_webhook_payload({"entry": "not-a-list"}) == []
    assert normalize_whatsapp_webhook_payload({"entry": [{"changes": [{"value": "bad"}]}]}) == []


@pytest.mark.asyncio
async def test_whatsapp_channel_sending_disabled() -> None:
    channel = WhatsAppChannel(Settings())
    result = await channel.send_message(
        message=OutgoingMessage(
            channel=ChannelName.WHATSAPP,
            external_user_ref="anon_user",
            text="Hi",
        )
    )

    assert result.sent is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_whatsapp_webhook_verification_success() -> None:
    settings = Settings(meta_verify_token="verify-token")
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-token",
                "hub.challenge": "challenge-value",
            },
        )

    assert response.status_code == 200
    assert response.text == "challenge-value"


@pytest.mark.asyncio
async def test_whatsapp_webhook_verification_rejects_bad_token() -> None:
    settings = Settings(meta_verify_token="verify-token")
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "bad-token",
                "hub.challenge": "challenge-value",
            },
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_whatsapp_webhook_post_does_not_send_reply() -> None:
    settings = Settings(meta_verify_token="verify-token")
    app = create_app(settings)
    payload = load_fixture("whatsapp_text_message.json")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/webhooks/whatsapp", json=payload)

    assert response.status_code == 200
    parsed = WhatsAppWebhookPostResponse.model_validate(response.json())
    assert parsed.messages_normalized == 1
    assert parsed.auto_reply_sent is False
