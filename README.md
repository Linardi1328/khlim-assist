# KHLIM Assist

KHLIM Assist is a multilingual AI assistant foundation for KHLIM Basketball event support. The long-term system will support WhatsApp, Instagram, English, Bahasa Melayu, Mandarin, mixed-language Malaysian conversations, FAQ answering, event-specific knowledge, context, escalation, PIC routing, registration/payment lookups, and auditability.

KHLIM Assist v0.1 Phase 0 does NOT send live participant replies.

## Current Status

This repository is at `v0.1 Phase 0: Foundation & Knowledge Architecture`.

Phase 0 provides a clean backend skeleton, database model layer, migrations, policy contracts, knowledge architecture, anonymized evaluation cases, tests, and developer documentation. Production bot behavior is intentionally deferred.

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
Response or Human Handoff
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
- `META_VERIFY_TOKEN`
- `META_ACCESS_TOKEN`
- `META_PHONE_NUMBER_ID`
- `META_APP_SECRET`
- `ACTIVE_EVENT_ID`

Blank Meta/OpenAI values are allowed in local and test mode. Calling credential-required functionality without credentials fails gracefully.

## Database

Start local PostgreSQL:

```bash
docker compose up -d db
```

Use this local development URL:

```bash
export DATABASE_URL="postgresql+asyncpg://khlim_assist@localhost:5432/khlim_assist"
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

## Lint And Type Checks

```bash
ruff check .
mypy backend/app
```

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

Phase 0 does not implement live automatic WhatsApp replies, Instagram integration, voice-note transcription, OCR, payment verification, registration-system lookup, merchandise stock lookup, admin dashboard, participant frontend, refunds, schedule changes, production deployment, or autonomous multi-agent workflows.

## Next Planned Phase

The next phase is `KHLIM Assist v0.1 Phase 1 — WhatsApp Sandbox Integration`.
