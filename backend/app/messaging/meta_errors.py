class MetaWhatsAppError(RuntimeError):
    """Base error for WhatsApp Cloud API transport failures."""


class MetaConfigurationError(MetaWhatsAppError):
    """Required Meta configuration is missing or invalid."""


class MetaAuthenticationError(MetaWhatsAppError):
    """Meta rejected authentication or authorization."""


class MetaRateLimitError(MetaWhatsAppError):
    """Meta rate-limited the request."""


class MetaRequestError(MetaWhatsAppError):
    """Meta rejected the request or returned an unusable response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class MetaTransportError(MetaWhatsAppError):
    """The Meta request could not be completed at the transport layer."""


class SandboxRecipientNotAllowed(MetaWhatsAppError):
    """Sandbox mode blocked a destination outside the allowlist."""


class OutboundMessagingDisabled(MetaWhatsAppError):
    """Outbound WhatsApp messaging is disabled by configuration."""
