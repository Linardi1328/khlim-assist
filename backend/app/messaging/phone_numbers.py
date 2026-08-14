import re

from app.messaging.meta_errors import MetaConfigurationError, SandboxRecipientNotAllowed

_SEPARATORS = re.compile(r"[\s\-().]+")


def normalize_phone_number(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("+"):
        stripped = stripped[1:]
    digits = _SEPARATORS.sub("", stripped)
    if not digits.isdigit() or not 8 <= len(digits) <= 15 or set(digits) == {"0"}:
        raise ValueError("Phone number must normalize to 8-15 digits")
    return digits


def normalize_allowed_recipients(values: tuple[str, ...]) -> frozenset[str]:
    normalized: set[str] = set()
    for value in values:
        try:
            normalized.add(normalize_phone_number(value))
        except ValueError as exc:
            raise MetaConfigurationError(
                "WHATSAPP_ALLOWED_RECIPIENTS contains an invalid entry"
            ) from exc
    return frozenset(normalized)


def ensure_recipient_allowed(
    recipient: str,
    allowed_recipients: tuple[str, ...],
) -> str:
    normalized = normalize_phone_number(recipient)
    allowed = normalize_allowed_recipients(allowed_recipients)
    if normalized not in allowed:
        raise SandboxRecipientNotAllowed("Recipient is not allowlisted for WhatsApp sandbox mode")
    return normalized
