import pytest
from app.messaging.meta_signature import (
    MetaSignatureVerificationError,
    compute_meta_signature,
    verify_meta_signature,
)


def test_valid_post_signature_is_accepted() -> None:
    body = b'{"object":"whatsapp_business_account"}'
    signature = compute_meta_signature(body, "fake-app-secret")

    verify_meta_signature(body, signature, "fake-app-secret")


def test_wrong_post_signature_is_rejected() -> None:
    body = b'{"object":"whatsapp_business_account"}'
    signature = compute_meta_signature(body, "fake-app-secret")

    with pytest.raises(MetaSignatureVerificationError):
        verify_meta_signature(body, signature, "different-secret")


def test_missing_post_signature_is_rejected() -> None:
    with pytest.raises(MetaSignatureVerificationError):
        verify_meta_signature(b"{}", None, "fake-app-secret")


def test_malformed_post_signature_is_rejected() -> None:
    with pytest.raises(MetaSignatureVerificationError):
        verify_meta_signature(b"{}", "sha1=not-supported", "fake-app-secret")


def test_body_changed_after_signature_generation_is_rejected() -> None:
    original_body = b'{"messages":["payload-a"]}'
    changed_body = b'{"messages":["payload-b"]}'
    signature = compute_meta_signature(original_body, "fake-app-secret")

    with pytest.raises(MetaSignatureVerificationError):
        verify_meta_signature(changed_body, signature, "fake-app-secret")
