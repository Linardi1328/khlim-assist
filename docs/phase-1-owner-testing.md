# Phase 1 Owner Testing Guide

Separate automated verification from live Meta verification. Automated tests do not prove the owner's Meta sandbox is configured correctly.

## Automated Verification

```bash
source .venv/bin/activate
ruff check .
mypy backend/app
POSTGRES_SMOKE_DATABASE_URL=postgresql+asyncpg://khlim_assist@localhost:5433/khlim_assist pytest
DATABASE_URL=postgresql+asyncpg://khlim_assist@localhost:5433/khlim_assist alembic upgrade head
```

Expected:

```text
ruff: PASS
mypy: PASS
pytest: PASS
alembic: PASS
```

## Live Meta Owner Verification

### Gate 1: Application Startup

Start PostgreSQL:

```bash
docker compose up -d db
```

Set local environment values:

```bash
export DATABASE_URL="postgresql+asyncpg://khlim_assist@localhost:5433/khlim_assist"
export META_GRAPH_API_VERSION="<META_GRAPH_API_VERSION>"
export META_WABA_ID="<META_WABA_ID>"
export META_PHONE_NUMBER_ID="<META_PHONE_NUMBER_ID>"
export META_ACCESS_TOKEN="<META_ACCESS_TOKEN>"
export META_VERIFY_TOKEN="<META_VERIFY_TOKEN>"
export META_APP_SECRET="<META_APP_SECRET>"
export WHATSAPP_SANDBOX_MODE=true
export WHATSAPP_OUTBOUND_ENABLED=false
export WHATSAPP_ALLOWED_RECIPIENTS=""
```

Run migrations and start the API:

```bash
alembic upgrade head
uvicorn app.main:app --reload --app-dir backend
```

Verify:

```bash
curl http://127.0.0.1:8000/health
```

Expected: JSON response with `"status":"ok"`.

### Gate 2: Webhook Verification

Expose the local API through HTTPS and configure Meta callback URL:

```text
https://<PUBLIC_HOST>/api/v1/webhooks/whatsapp
```

Use the same verification token configured in `META_VERIFY_TOKEN`.

Expected: Meta accepts webhook verification.

### Gate 3: Inbound Message

From an approved sandbox/test WhatsApp participant, send:

```text
KHLIM Assist Phase 1 inbound test
```

Expected:

```text
Meta delivers webhook
signature accepted
Conversation created
Message created
text persisted
no outbound message sent
```

Inspect stored messages:

```bash
python -m app.scripts.whatsapp_recent --limit 10
```

### Gate 4: Duplicate Webhook

Automated tests cover duplicate webhook behavior. To manually inspect recent state after a Meta retry, run:

```bash
python -m app.scripts.whatsapp_recent --limit 10
```

Expected: the same external WhatsApp message ID appears once.

### Gate 5: Controlled Outbound

Enable outbound only for the owner-controlled allowlisted number:

```bash
export WHATSAPP_OUTBOUND_ENABLED=true
export WHATSAPP_SANDBOX_MODE=true
export WHATSAPP_ALLOWED_RECIPIENTS="<OWNER_TEST_NUMBER>"
```

Send a text test:

```bash
python -m app.scripts.whatsapp_send_test \
  --to "<OWNER_TEST_NUMBER>" \
  --text "KHLIM Assist sandbox test"
```

Optional template test:

```bash
python -m app.scripts.whatsapp_send_test \
  --to "<OWNER_TEST_NUMBER>" \
  --template hello_world \
  --language en_US
```

Expected:

```text
Meta accepts message
external message ID printed
outbound Message persisted
message appears on approved test phone
```

### Gate 6: Delivery Status

After the outbound message is delivered/read, run:

```bash
python -m app.scripts.whatsapp_recent --limit 10
```

Expected eventually:

```text
DELIVERED
```

Where available:

```text
READ
```

The stored message should keep the highest known status and not regress on out-of-order webhooks.

### Gate 7: Outbound Disabled

Disable outbound:

```bash
export WHATSAPP_OUTBOUND_ENABLED=false
```

Attempt a send:

```bash
python -m app.scripts.whatsapp_send_test \
  --to "<OWNER_TEST_NUMBER>" \
  --text "This should be blocked"
```

Expected:

```text
BLOCKED LOCALLY
```

No Meta request should be made.

### Gate 8: Recipient Allowlist

With sandbox mode enabled and outbound enabled, try a number not in `WHATSAPP_ALLOWED_RECIPIENTS`:

```bash
python -m app.scripts.whatsapp_send_test \
  --to "<NON_ALLOWLISTED_TEST_NUMBER>" \
  --text "This should be blocked"
```

Expected:

```text
BLOCKED
```

No Meta request should be made.

### Gate 9: No AI Reply

Send another inbound message:

```text
How much is U16?
```

Expected:

```text
message stored
NO AI call
NO automatic response
```

This confirms Phase 1 remains transport-only.
