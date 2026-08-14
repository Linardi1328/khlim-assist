import hashlib
import hmac


class MetaSignatureVerificationError(ValueError):
    """Raised when a Meta webhook signature is missing or invalid."""


def compute_meta_signature(raw_body: bytes, app_secret: str) -> str:
    digest = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_meta_signature(raw_body: bytes, signature_header: str | None, app_secret: str) -> None:
    if not signature_header:
        raise MetaSignatureVerificationError("Missing Meta signature")
    if not signature_header.startswith("sha256="):
        raise MetaSignatureVerificationError("Malformed Meta signature")

    provided_digest = signature_header.removeprefix("sha256=")
    if len(provided_digest) != 64:
        raise MetaSignatureVerificationError("Malformed Meta signature")

    expected_signature = compute_meta_signature(raw_body, app_secret)
    if not hmac.compare_digest(signature_header, expected_signature):
        raise MetaSignatureVerificationError("Invalid Meta signature")
