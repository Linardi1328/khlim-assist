from typing import Any

import httpx

from app.config.settings import Settings, get_settings
from app.messaging.meta_errors import (
    MetaAuthenticationError,
    MetaConfigurationError,
    MetaRateLimitError,
    MetaRequestError,
    MetaTransportError,
    OutboundMessagingDisabled,
)
from app.messaging.phone_numbers import ensure_recipient_allowed, normalize_phone_number


class WhatsAppSendResponse:
    def __init__(self, provider_message_id: str) -> None:
        self.provider_message_id = provider_message_id


class WhatsAppCloudClient:
    def __init__(
        self,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.http_client = http_client

    async def send_text_message(self, to: str, text: str) -> WhatsAppSendResponse:
        recipient = self._validate_send_configuration(to)
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        return await self._post_message(payload)

    async def send_template_message(
        self,
        to: str,
        template_name: str,
        language_code: str,
    ) -> WhatsAppSendResponse:
        recipient = self._validate_send_configuration(to)
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }
        return await self._post_message(payload)

    def _validate_send_configuration(self, to: str) -> str:
        if not self.settings.whatsapp_outbound_enabled:
            raise OutboundMessagingDisabled("WhatsApp outbound messaging is disabled")
        if not self.settings.meta_access_token:
            raise MetaConfigurationError("META_ACCESS_TOKEN is required for WhatsApp outbound")
        if not self.settings.meta_phone_number_id:
            raise MetaConfigurationError("META_PHONE_NUMBER_ID is required for WhatsApp outbound")
        if not self.settings.meta_graph_api_version:
            raise MetaConfigurationError("META_GRAPH_API_VERSION is required for WhatsApp outbound")

        if self.settings.whatsapp_sandbox_mode:
            return ensure_recipient_allowed(to, self.settings.whatsapp_allowed_recipients)
        return normalize_phone_number(to)

    def _message_url(self) -> str:
        if not self.settings.meta_phone_number_id or not self.settings.meta_graph_api_version:
            raise MetaConfigurationError("Meta Graph API version and phone number ID are required")
        base_url = self.settings.meta_graph_api_base_url.rstrip("/")
        version = self.settings.meta_graph_api_version.strip("/")
        return f"{base_url}/{version}/{self.settings.meta_phone_number_id}/messages"

    async def _post_message(self, payload: dict[str, Any]) -> WhatsAppSendResponse:
        headers = {"Authorization": f"Bearer {self.settings.meta_access_token}"}
        timeout = httpx.Timeout(self.settings.whatsapp_request_timeout_seconds)
        try:
            if self.http_client is not None:
                response = await self.http_client.post(
                    self._message_url(),
                    json=payload,
                    headers=headers,
                )
            else:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        self._message_url(),
                        json=payload,
                        headers=headers,
                    )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise MetaTransportError("Meta WhatsApp request failed at transport layer") from exc

        if response.status_code in {401, 403}:
            raise MetaAuthenticationError("Meta rejected WhatsApp authentication")
        if response.status_code == 429:
            raise MetaRateLimitError("Meta rate limit reached")
        if response.status_code >= 400:
            raise MetaRequestError("Meta WhatsApp request failed", status_code=response.status_code)

        try:
            data = response.json()
        except ValueError as exc:
            raise MetaRequestError("Meta returned a malformed JSON response") from exc

        provider_message_id = self._extract_message_id(data)
        if not provider_message_id:
            raise MetaRequestError("Meta response did not include a provider message ID")
        return WhatsAppSendResponse(provider_message_id=provider_message_id)

    def _extract_message_id(self, data: object) -> str | None:
        if not isinstance(data, dict):
            return None
        messages = data.get("messages")
        if not isinstance(messages, list) or not messages:
            return None
        first_message = messages[0]
        if not isinstance(first_message, dict):
            return None
        message_id = first_message.get("id")
        if isinstance(message_id, str) and message_id:
            return message_id
        return None
