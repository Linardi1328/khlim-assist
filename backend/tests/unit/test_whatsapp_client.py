import httpx
import pytest
from app.config.settings import Settings
from app.messaging.meta_errors import (
    MetaAuthenticationError,
    MetaConfigurationError,
    MetaRateLimitError,
    MetaRequestError,
    MetaTransportError,
    OutboundMessagingDisabled,
    SandboxRecipientNotAllowed,
)
from app.messaging.phone_numbers import normalize_phone_number
from app.messaging.whatsapp_client import WhatsAppCloudClient


def enabled_settings() -> Settings:
    return Settings(
        meta_graph_api_version="v20.0",
        meta_access_token="fake-token",
        meta_phone_number_id="fake-phone-number-id",
        whatsapp_outbound_enabled=True,
        whatsapp_sandbox_mode=True,
        whatsapp_allowed_recipients=("15550000001",),
    )


def success_client(calls: list[httpx.Request]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"messages": [{"id": "wamid.synthetic_outbound_1"}]})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_phone_number_normalization() -> None:
    assert normalize_phone_number("+1 555-000-0001") == "15550000001"
    assert normalize_phone_number("15550000001") == "15550000001"
    with pytest.raises(ValueError):
        normalize_phone_number("abc")


@pytest.mark.asyncio
async def test_outbound_disabled_blocks_before_http() -> None:
    calls: list[httpx.Request] = []
    client = WhatsAppCloudClient(Settings(), success_client(calls))

    with pytest.raises(OutboundMessagingDisabled):
        await client.send_text_message("15550000001", "test")

    assert calls == []


@pytest.mark.asyncio
async def test_sandbox_recipient_not_allowlisted_blocks_before_http() -> None:
    calls: list[httpx.Request] = []
    client = WhatsAppCloudClient(enabled_settings(), success_client(calls))

    with pytest.raises(SandboxRecipientNotAllowed):
        await client.send_text_message("15550000002", "test")

    assert calls == []


@pytest.mark.asyncio
async def test_allowlisted_text_send_invokes_external_client() -> None:
    calls: list[httpx.Request] = []
    http_client = success_client(calls)
    client = WhatsAppCloudClient(enabled_settings(), http_client)

    response = await client.send_text_message("+1 555-000-0001", "sandbox test")

    assert response.provider_message_id == "wamid.synthetic_outbound_1"
    assert len(calls) == 1
    assert calls[0].url.path == "/v20.0/fake-phone-number-id/messages"
    assert calls[0].headers["authorization"] == "Bearer fake-token"
    await http_client.aclose()


@pytest.mark.asyncio
async def test_successful_template_send() -> None:
    calls: list[httpx.Request] = []
    http_client = success_client(calls)
    client = WhatsAppCloudClient(enabled_settings(), http_client)

    response = await client.send_template_message("15550000001", "hello_world", "en_US")

    assert response.provider_message_id == "wamid.synthetic_outbound_1"
    assert len(calls) == 1
    assert b"hello_world" in calls[0].content
    await http_client.aclose()


@pytest.mark.asyncio
async def test_missing_meta_token_is_configuration_error() -> None:
    settings = enabled_settings().model_copy(update={"meta_access_token": None})
    client = WhatsAppCloudClient(settings, success_client([]))

    with pytest.raises(MetaConfigurationError):
        await client.send_text_message("15550000001", "test")


@pytest.mark.asyncio
async def test_missing_phone_number_id_is_configuration_error() -> None:
    settings = enabled_settings().model_copy(update={"meta_phone_number_id": None})
    client = WhatsAppCloudClient(settings, success_client([]))

    with pytest.raises(MetaConfigurationError):
        await client.send_text_message("15550000001", "test")


async def assert_status_error(status_code: int, expected_error: type[Exception]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": {"message": "synthetic error"}})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = WhatsAppCloudClient(enabled_settings(), http_client)
    with pytest.raises(expected_error):
        await client.send_text_message("15550000001", "test")
    await http_client.aclose()


@pytest.mark.asyncio
async def test_401_403_authentication_errors() -> None:
    await assert_status_error(401, MetaAuthenticationError)
    await assert_status_error(403, MetaAuthenticationError)


@pytest.mark.asyncio
async def test_400_request_error() -> None:
    await assert_status_error(400, MetaRequestError)


@pytest.mark.asyncio
async def test_429_rate_limit_error() -> None:
    await assert_status_error(429, MetaRateLimitError)


@pytest.mark.asyncio
async def test_500_request_error() -> None:
    await assert_status_error(500, MetaRequestError)


@pytest.mark.asyncio
async def test_network_timeout_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("synthetic timeout")

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = WhatsAppCloudClient(enabled_settings(), http_client)
    with pytest.raises(MetaTransportError):
        await client.send_text_message("15550000001", "test")
    await http_client.aclose()


@pytest.mark.asyncio
async def test_malformed_provider_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json")

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = WhatsAppCloudClient(enabled_settings(), http_client)
    with pytest.raises(MetaRequestError):
        await client.send_text_message("15550000001", "test")
    await http_client.aclose()


@pytest.mark.asyncio
async def test_missing_returned_message_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"messages": [{}]})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = WhatsAppCloudClient(enabled_settings(), http_client)
    with pytest.raises(MetaRequestError):
        await client.send_text_message("15550000001", "test")
    await http_client.aclose()
