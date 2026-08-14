import hmac
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings, get_settings
from app.db.session import get_db_session
from app.messaging.meta_signature import (
    MetaSignatureVerificationError,
    verify_meta_signature,
)
from app.messaging.whatsapp import (
    normalize_whatsapp_status_payload,
    normalize_whatsapp_webhook_payload,
)
from app.services.whatsapp_ingestion import (
    WhatsAppWebhookProcessingResult,
    WhatsAppWebhookProcessor,
)

router = APIRouter(prefix="/webhooks/whatsapp", tags=["webhooks"])


@router.get("", response_class=PlainTextResponse)
async def verify_whatsapp_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    settings: Settings = Depends(get_settings),
) -> PlainTextResponse:
    if settings.meta_verify_token is None:
        raise HTTPException(status_code=503, detail="Meta verify token is not configured")
    if hub_mode != "subscribe" or hub_verify_token is None:
        raise HTTPException(status_code=403, detail="Invalid webhook verification request")
    if not hmac.compare_digest(hub_verify_token, settings.meta_verify_token):
        raise HTTPException(status_code=403, detail="Invalid verify token")
    if hub_challenge is None:
        raise HTTPException(status_code=400, detail="Missing challenge")
    return PlainTextResponse(hub_challenge)


@router.post("", response_model=WhatsAppWebhookProcessingResult)
async def receive_whatsapp_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_db_session),
) -> WhatsAppWebhookProcessingResult:
    if settings.meta_app_secret is None:
        raise HTTPException(status_code=503, detail="Meta app secret is not configured")

    raw_body = await request.body()
    signature_header = request.headers.get("x-hub-signature-256")
    try:
        verify_meta_signature(raw_body, signature_header, settings.meta_app_secret)
    except MetaSignatureVerificationError as exc:
        raise HTTPException(status_code=403, detail="Invalid Meta signature") from exc

    try:
        parsed_payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Malformed JSON payload") from exc
    if not isinstance(parsed_payload, dict):
        raise HTTPException(status_code=400, detail="Webhook payload must be a JSON object")

    payload: dict[str, Any] = parsed_payload
    messages = normalize_whatsapp_webhook_payload(payload)
    statuses = normalize_whatsapp_status_payload(payload)
    processor = WhatsAppWebhookProcessor(settings)
    return await processor.process(session, messages, statuses)
