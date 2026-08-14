import json
from pathlib import Path

import httpx
import pytest
from app.ai.openai_client import OpenAIProvider
from app.config.settings import Settings, get_settings
from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.db.session import get_db_session
from app.main import create_app
from app.messaging.base import OutgoingMessage
from app.messaging.meta_signature import compute_meta_signature
from app.messaging.whatsapp import (
    WhatsAppChannel,
    normalize_whatsapp_status_payload,
    normalize_whatsapp_webhook_payload,
)
from app.messaging.whatsapp_client import WhatsAppCloudClient
from app.schemas.enums import ChannelName, ContentType, MessageDirection
from app.services.whatsapp_ingestion import WhatsAppWebhookProcessingResult
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def load_fixture(name: str) -> dict[str, object]:
    return json.loads(Path("backend/tests/fixtures", name).read_text(encoding="utf-8"))


def signed_body(payload: dict[str, object], app_secret: str) -> tuple[bytes, dict[str, str]]:
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return raw_body, {"x-hub-signature-256": compute_meta_signature(raw_body, app_secret)}


def app_with_db(settings: Settings, db_session: AsyncSession) -> object:
    app = create_app(settings)

    async def override_session() -> object:
        yield db_session

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db_session] = override_session
    return app


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


def test_whatsapp_status_payload_normalization() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "phone-id"},
                            "statuses": [
                                {
                                    "id": "wamid.synthetic_outbound_1",
                                    "status": "delivered",
                                    "timestamp": "1799999999",
                                    "recipient_id": "15550000001",
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }

    statuses = normalize_whatsapp_status_payload(payload)

    assert len(statuses) == 1
    assert statuses[0].external_message_id == "wamid.synthetic_outbound_1"
    assert statuses[0].status == "delivered"
    assert statuses[0].phone_number_id == "phone-id"


def test_whatsapp_failed_status_numeric_error_code_normalization() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "phone-id"},
                            "statuses": [
                                {
                                    "id": "wamid.synthetic_failed_1",
                                    "status": "failed",
                                    "timestamp": "1799999999",
                                    "recipient_id": "15550000001",
                                    "errors": [
                                        {
                                            "code": 131014,
                                            "title": "Synthetic failure",
                                        }
                                    ],
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }

    statuses = normalize_whatsapp_status_payload(payload)

    assert len(statuses) == 1
    assert statuses[0].provider_error_code == "131014"
    assert statuses[0].provider_error_message == "Synthetic failure"


def test_whatsapp_failed_status_string_error_code_normalization() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "statuses": [
                                {
                                    "id": "wamid.synthetic_failed_2",
                                    "status": "failed",
                                    "errors": [
                                        {
                                            "code": "131014",
                                            "message": "Synthetic message failure",
                                        }
                                    ],
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }

    statuses = normalize_whatsapp_status_payload(payload)

    assert len(statuses) == 1
    assert statuses[0].provider_error_code == "131014"
    assert statuses[0].provider_error_message == "Synthetic message failure"


def test_whatsapp_payload_normalization_handles_malformed_payload() -> None:
    assert normalize_whatsapp_webhook_payload({"entry": "not-a-list"}) == []
    assert normalize_whatsapp_webhook_payload({"entry": [{"changes": [{"value": "bad"}]}]}) == []


def test_whatsapp_payload_normalization_ignores_missing_sender() -> None:
    payload = load_fixture("whatsapp_text_message.json")
    message = payload["entry"][0]["changes"][0]["value"]["messages"][0]  # type: ignore[index]
    del message["from"]

    assert normalize_whatsapp_webhook_payload(payload) == []


def test_whatsapp_payload_normalization_ignores_media_message() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "anon_whatsapp_user_1",
                                    "id": "wamid.synthetic_image_1",
                                    "type": "image",
                                    "image": {"id": "synthetic_media_id"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    assert normalize_whatsapp_webhook_payload(payload) == []


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
async def test_whatsapp_webhook_verification_missing_configuration() -> None:
    settings = Settings(meta_verify_token="")
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "anything",
                "hub.challenge": "challenge-value",
            },
        )

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_whatsapp_webhook_post_persists_and_does_not_send_reply(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_meta_send(*args: object, **kwargs: object) -> object:
        raise AssertionError("Inbound webhook must not send Meta outbound messages")

    async def fail_openai_interpret(*args: object, **kwargs: object) -> object:
        raise AssertionError("Inbound webhook must not invoke OpenAI interpretation")

    monkeypatch.setattr(WhatsAppCloudClient, "send_text_message", fail_meta_send)
    monkeypatch.setattr(OpenAIProvider, "interpret_message", fail_openai_interpret)

    settings = Settings(
        meta_verify_token="verify-token",
        meta_app_secret="test-secret",
        ai_processing_enabled=True,
        ai_auto_reply_enabled=True,
    )
    app = app_with_db(settings, db_session)
    payload = load_fixture("whatsapp_text_message.json")
    raw_body, headers = signed_body(payload, "test-secret")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/webhooks/whatsapp",
            content=raw_body,
            headers=headers,
        )

    assert response.status_code == 200
    parsed = WhatsAppWebhookProcessingResult.model_validate(response.json())
    assert parsed.messages_normalized == 1
    assert parsed.messages_persisted == 1
    assert parsed.auto_reply_sent is False

    conversations = list(await db_session.scalars(select(Conversation)))
    messages = list(await db_session.scalars(select(Message)))
    assert len(conversations) == 1
    assert len(messages) == 1
    assert messages[0].direction == MessageDirection.INBOUND
    assert messages[0].text_content == "Where do I register?"


@pytest.mark.asyncio
async def test_whatsapp_webhook_post_rejects_missing_signature(
    db_session: AsyncSession,
) -> None:
    settings = Settings(meta_app_secret="test-secret")
    app = app_with_db(settings, db_session)
    payload = load_fixture("whatsapp_text_message.json")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/webhooks/whatsapp", json=payload)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_whatsapp_webhook_post_rejects_wrong_signature(
    db_session: AsyncSession,
) -> None:
    settings = Settings(meta_app_secret="test-secret")
    app = app_with_db(settings, db_session)
    payload = load_fixture("whatsapp_text_message.json")
    raw_body, _headers = signed_body(payload, "test-secret")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/webhooks/whatsapp",
            content=raw_body,
            headers={"x-hub-signature-256": compute_meta_signature(raw_body, "wrong-secret")},
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_whatsapp_webhook_post_rejects_malformed_signature(
    db_session: AsyncSession,
) -> None:
    settings = Settings(meta_app_secret="test-secret")
    app = app_with_db(settings, db_session)
    payload = load_fixture("whatsapp_text_message.json")
    raw_body = json.dumps(payload).encode("utf-8")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/webhooks/whatsapp",
            content=raw_body,
            headers={"x-hub-signature-256": "sha256=bad"},
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_whatsapp_webhook_post_rejects_changed_body_after_signature(
    db_session: AsyncSession,
) -> None:
    settings = Settings(meta_app_secret="test-secret")
    app = app_with_db(settings, db_session)
    payload = load_fixture("whatsapp_text_message.json")
    raw_body, headers = signed_body(payload, "test-secret")
    changed_body = raw_body.replace(b"Where do I register?", b"How much is U16?")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/webhooks/whatsapp",
            content=changed_body,
            headers=headers,
        )

    assert response.status_code == 403
