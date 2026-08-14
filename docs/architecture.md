# Architecture

KHLIM Assist v0.1 Phase 0 establishes the backend foundation only. It does not send live participant replies.

## Flow

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

## Core Principle

```text
Rules decide.
AI communicates.
```

The AI layer may interpret participant language and draft friendly responses, but it must not decide permissions. Refunds, exceptions, schedule changes, reserved slots, withdrawals, disciplinary issues, and special eligibility decisions belong to deterministic policy and human authority.

## Components

- `backend/app/messaging`: channel-neutral inbound/outbound message abstractions.
- `backend/app/api/webhooks`: provider-specific webhook adapters. Phase 0 includes WhatsApp parsing only.
- `backend/app/ai`: provider abstraction plus a lazy OpenAI SDK wrapper. No external calls happen at startup.
- `backend/app/policy`: deterministic decision and routing rules.
- `backend/app/db/models`: PostgreSQL-compatible SQLAlchemy models for events, FAQs, rules, conversations, messages, handoffs, PIC roles, and audit logs.
- `knowledge`: generalized FAQ taxonomy, sample event configuration, escalation policy, response style, and synthetic evaluation cases.

## Decision Levels

- `GREEN`: approved knowledge/rule exists and the request is complete enough to answer.
- `YELLOW`: clarification or trusted lookup is required.
- `RED`: human authority is required.

Phase 0 stops before live automated replies. Future phases can connect a WhatsApp sandbox, trusted registration/payment systems, and authorized human workflows.

## Phase 1 Transport Boundary

Phase 1 adds secure WhatsApp sandbox transport and persistence, but still stops before AI.

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

Future Phase 2 work may continue:

```text
AI Interpretation
    ↓
Knowledge Retrieval
    ↓
Decision Engine
```

Automatic participant replies remain disabled in Phase 1.
