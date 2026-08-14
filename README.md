# KHLIM Assist

KHLIM Assist is a multilingual AI assistant foundation for KHLIM Basketball event support. The long-term system will support WhatsApp, Instagram, English, Bahasa Melayu, Mandarin, mixed-language Malaysian conversations, FAQ answering, event-specific knowledge, context, escalation, PIC routing, registration/payment lookups, and auditability.

KHLIM Assist v0.1 Phase 2 implements AI FAQ interpretation, approved knowledge retrieval, deterministic decisions, and draft response generation.

AI participant auto-replies remain disabled.

## Current Status

This repository is at `KHLIM Assist v0.1 Phase 2 — AI FAQ Engine`.

Phase 2 proves the reasoning layer: multilingual interpretation, multi-intent extraction, typed knowledge retrieval, GREEN/YELLOW/RED policy decisions, and KHLIM-style draft responses. WhatsApp AI auto-replies remain intentionally disabled.

## Phase 0 Scope

- FastAPI backend skeleton
- Typed environment settings
- PostgreSQL-compatible SQLAlchemy models
- Alembic migration
- Health endpoint
- Versioned API scaffolding
- WhatsApp webhook verification and inbound text normalization
- Channel-neutral messaging abstraction
- Lazy OpenAI SDK provider abstraction
- Deterministic GREEN/YELLOW/RED decision engine
- PIC routing
- FAQ master, sample event config, response style, escalation policy, evaluation fixtures
- Unit and integration tests
- Security, architecture, taxonomy, and acceptance docs

## Phase 1 Scope

- WhatsApp webhook POST signature verification
- inbound text message persistence
- conversation creation/reuse
- duplicate message protection by provider message ID
- configured phone-number ID scoping
- guarded WhatsApp Cloud API client
- outbound disabled-by-default safety switch
- sandbox recipient allowlist
- manual owner-controlled send CLI
- read-only recent WhatsApp message CLI
- outbound message persistence and provider message ID tracking
- sent/delivered/read/failed delivery status tracking
- safe Meta API error handling
- PostgreSQL migration and smoke tests
- Meta sandbox setup and owner testing documentation

## Phase 2 Scope

- OpenAI Responses API provider behind the existing AI abstraction
- fail-closed AI settings with processing disabled by default
- deterministic conversation context builder with bounded recent text messages
- typed knowledge query/result/evidence objects
- DB-first approved knowledge retrieval from Event, FAQEntry, and EventRule records
- DecisionEngine integration using typed evidence
- KHLIM-style draft response generation
- AIProcessingRun persistence for completed, failed, skipped, and pending runs
- manual shadow-processing CLI for one stored message
- recent AI analysis CLI
- synthetic evaluation runner over `knowledge/evaluation_cases.json`
- PostgreSQL migration and smoke test for AI analysis persistence
- prompt-injection and no-auto-send boundary tests

## Architecture Overview

```text
Participant
     ↓
Messaging Channel
     ↓
Webhook / Message Adapter
     ↓
Message Normalization
     ↓
Conversation Context
     ↓
AI Interpretation
     ↓
Knowledge / Rule Retrieval
     ↓
Deterministic Policy Engine
     ↓
GREEN / YELLOW / RED
     ↓
Draft Response Stored
     ↓
[STOP HERE IN PHASE 2]
```

Future phases continue only after explicit approval:

```text
Human Handoff Workflow / Authorized Sending
```

Rules decide. AI communicates.

## Repository Layout

```text
backend/app           FastAPI application code
backend/tests         Unit and integration tests
alembic               Database migrations
knowledge             Generalized knowledge and evaluation contracts
docs                  Architecture, security, taxonomy, acceptance docs
```

## Local Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Copy environment placeholders:

```bash
cp .env.example .env
```

Do not add real production secrets to source control.

## Environment Variables

- `APP_ENV`
- `APP_NAME`
- `LOG_LEVEL`
- `DATABASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_REQUEST_TIMEOUT_SECONDS`
- `AI_PROCESSING_ENABLED`
- `AI_SHADOW_MODE`
- `AI_AUTO_REPLY_ENABLED`
- `AI_CONTEXT_MESSAGE_LIMIT`
- `META_GRAPH_API_BASE_URL`
- `META_GRAPH_API_VERSION`
- `META_WABA_ID`
- `META_VERIFY_TOKEN`
- `META_ACCESS_TOKEN`
- `META_PHONE_NUMBER_ID`
- `META_APP_SECRET`
- `WHATSAPP_SANDBOX_MODE`
- `WHATSAPP_OUTBOUND_ENABLED`
- `WHATSAPP_ALLOWED_RECIPIENTS`
- `ACTIVE_EVENT_ID`

Blank Meta/OpenAI values are allowed in local and test mode. Calling credential-required functionality without credentials fails gracefully.

## Database

Start local PostgreSQL:

```bash
docker compose up -d db
```

Use this local development URL:

```bash
export DATABASE_URL="postgresql+asyncpg://khlim_assist@localhost:5433/khlim_assist"
```

Run migrations:

```bash
alembic upgrade head
```

If `DATABASE_URL` is blank, the app falls back to a local SQLite database for lightweight development and tests.

## Running The API

```bash
uvicorn app.main:app --reload --app-dir backend
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## API Surface

- `GET /health`
- `GET /api/v1/events`
- `GET /api/v1/events/{id}`
- `GET /api/v1/conversations/{id}`
- `GET /api/v1/handoffs`
- `GET /api/v1/handoffs/{id}`
- `GET /api/v1/webhooks/whatsapp`
- `POST /api/v1/webhooks/whatsapp`

Authentication and authorization must be added before any production admin exposure.

## Running Tests

```bash
pytest
```

Run PostgreSQL smoke tests:

```bash
POSTGRES_SMOKE_DATABASE_URL="postgresql+asyncpg://khlim_assist@localhost:5433/khlim_assist" pytest
```

## Lint And Type Checks

```bash
ruff check .
mypy backend/app
```

## WhatsApp Owner CLIs

Send a controlled sandbox test message:

```bash
python -m app.scripts.whatsapp_send_test \
  --to "<TEST_NUMBER>" \
  --text "KHLIM Assist sandbox test"
```

Inspect recent stored WhatsApp messages:

```bash
python -m app.scripts.whatsapp_recent --limit 10
```

## AI Shadow CLIs

Process one stored message through Phase 2 shadow analysis:

```bash
python -m app.scripts.ai_process_message --message-id "<MESSAGE_UUID>"
```

Use the deterministic local provider for synthetic testing:

```bash
python -m app.scripts.ai_process_message --message-id "<MESSAGE_UUID>" --provider fake
```

Inspect recent AI analyses:

```bash
python -m app.scripts.ai_recent --limit 10
```

Run deterministic evaluation fixtures:

```bash
python -m app.scripts.ai_eval --provider fake
```

All Phase 2 AI outputs are stored drafts only. `AI_AUTO_REPLY_ENABLED=true` does not connect drafts to WhatsApp outbound sending in Phase 2.

## Privacy Principles

- Keep KHLIM knowledge separate from participant data.
- Do not commit real API keys, access tokens, phone numbers, participant identities, IC/passport numbers, payment details, or raw WhatsApp conversations.
- Use only anonymized or synthetic examples in tests and knowledge fixtures.
- Avoid logging raw sensitive participant content.

## Decision Levels

- `GREEN`: approved FAQ/rule can answer automatically when data is complete and confirmed.
- `YELLOW`: clarification or trusted lookup is required.
- `RED`: human authority is required.

## Current Limitations

Phase 2 does not implement live automatic WhatsApp replies, production OpenAI background processing, human handoff workflow, PIC dashboard, registration lookup, payment lookup, Instagram integration, voice-note transcription, OCR, merchandise stock lookup, participant frontend, refunds, schedule changes, production deployment, marketing sends, broadcasts, or autonomous workflows.

## Next Planned Phase

The next phase should build the human handoff workflow and reviewer-approved operational controls. Do not begin it until Phase 2 owner live OpenAI testing and review are complete.
