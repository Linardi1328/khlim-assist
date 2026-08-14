import hmac
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.config.settings import Settings, get_settings
from app.messaging.whatsapp import normalize_whatsapp_webhook_payload

router = APIRouter(prefix="/webhooks/whatsapp", tags=["webhooks"])


class WhatsAppWebhookPostResponse(BaseModel):
    received: bool
    messages_normalized: int
    auto_reply_sent: bool = False


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


@router.post("", response_model=WhatsAppWebhookPostResponse)
async def receive_whatsapp_webhook(
    payload: dict[str, Any] = Body(...),
) -> WhatsAppWebhookPostResponse:
    normalized = normalize_whatsapp_webhook_payload(payload)
    return WhatsAppWebhookPostResponse(
        received=True,
        messages_normalized=len(normalized),
        auto_reply_sent=False,
    )
