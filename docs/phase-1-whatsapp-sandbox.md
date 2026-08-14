# Phase 1 WhatsApp Sandbox Setup

Phase 1 proves secure WhatsApp Cloud API transport in a Meta sandbox/development environment.

It does not enable automatic FAQ replies, OpenAI inbound processing, or production WhatsApp deployment.

## Required Meta Values

Configure these locally in `.env` or the shell. Do not commit real values.

```text
META_GRAPH_API_VERSION=
META_WABA_ID=
META_PHONE_NUMBER_ID=
META_ACCESS_TOKEN=
META_VERIFY_TOKEN=
META_APP_SECRET=
```

Also configure outbound guardrails:

```text
WHATSAPP_SANDBOX_MODE=true
WHATSAPP_OUTBOUND_ENABLED=false
WHATSAPP_ALLOWED_RECIPIENTS=
```

`META_GRAPH_API_VERSION` is configuration-driven. Application code builds URLs from configuration rather than hard-coding a permanent Graph API version.

## Webhook URL

The webhook path is:

```text
/api/v1/webhooks/whatsapp
```

For local Meta testing, the FastAPI app must be reachable through a public HTTPS URL:

```text
https://<PUBLIC_HOST>/api/v1/webhooks/whatsapp
```

Use an HTTPS development tunnel or equivalent secure public callback during local testing. The application does not depend on a tunnel vendor.

## Verification

Meta will call:

```text
GET /api/v1/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...
```

The local `META_VERIFY_TOKEN` must match the token configured in Meta.

## Signature Verification

Phase 1 requires `X-Hub-Signature-256` validation for webhook POSTs.

The application:

1. Reads the raw body bytes.
2. Verifies HMAC SHA-256 using `META_APP_SECRET`.
3. Parses JSON only after the signature is valid.
4. Rejects missing, malformed, wrong, or changed-body signatures.

`META_APP_SECRET` is never logged or returned.

## Phone Number Scoping

If `META_PHONE_NUMBER_ID` is configured, signed inbound webhooks are processed only when their webhook metadata phone number ID matches the configured value.

Mismatched phone-number IDs are acknowledged safely, audited with non-sensitive metadata, and ignored.

## Phase Boundary

Phase 1 stops here:

```text
WhatsApp
    ↓
Meta Cloud API
    ↓
Signed Webhook
    ↓
WhatsApp Adapter
    ↓
Conversation + Message DB
    ↓
[STOP HERE]
```

Future phases may add:

```text
AI Interpretation
    ↓
Knowledge Retrieval
    ↓
Decision Engine
```

That boundary is intentionally not crossed in Phase 1.
