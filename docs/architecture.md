# Architecture

KHLIM Assist v0.1 Phase 2 establishes the WhatsApp transport and AI FAQ reasoning foundation. It does not send live participant AI replies.

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
Draft Response Stored
     ↓
[STOP HERE IN PHASE 2]
```

## Core Principle

```text
Rules decide.
AI communicates.
```

The AI layer may interpret participant language and draft friendly responses, but it must not decide permissions or source tournament facts. Refunds, exceptions, schedule changes, reserved slots, withdrawals, disciplinary issues, and special eligibility decisions belong to deterministic policy and human authority.

## Components

- `backend/app/messaging`: channel-neutral inbound/outbound message abstractions.
- `backend/app/api/webhooks`: provider-specific webhook adapters. Phase 1 includes signed WhatsApp webhook receive.
- `backend/app/ai`: provider abstraction, lazy OpenAI/Groq Responses API wrappers, context builder, typed knowledge retrieval, response drafting, and evaluation support.
- `backend/app/policy`: deterministic decision and routing rules.
- `backend/app/db/models`: PostgreSQL-compatible SQLAlchemy models for events, FAQs, rules, conversations, messages, handoffs, PIC roles, audit logs, and AI processing runs.
- `knowledge`: generalized FAQ taxonomy, sample event configuration, escalation policy, response style, and synthetic evaluation cases.

## Decision Levels

- `GREEN`: approved knowledge/rule exists and the request is complete enough to answer.
- `YELLOW`: clarification or trusted lookup is required.
- `RED`: human authority is required.

Phase 2 stops before live automated replies. Future phases can connect trusted registration/payment systems and authorized human workflows.

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

Phase 2 continues manually or through an explicit shadow-processing command:

```text
AI Interpretation
    ↓
Knowledge Retrieval
    ↓
Decision Engine
    ↓
Draft Stored
    ↓
[STOP HERE]
```

Automatic participant replies remain disabled in Phase 2. `AI_AUTO_REPLY_ENABLED` is not wired to WhatsApp outbound sending.

## Phase 2 AI FAQ Boundary

```text
Participant message
     ↓
Conversation + Message DB
     ↓
Manual Shadow Processor
     ↓
Bounded Conversation Context
     ↓
AI Interpretation
     ↓
Approved Knowledge Retrieval
     ↓
DecisionEngine
     ↓
Draft Response
     ↓
AIProcessingRun
```

The LLM may classify intent and draft participant-friendly wording. It is never the source of truth for fees, dates, venues, eligibility rules, payment status, or registration status. Those values must come from approved event data, FAQEntry, EventRule, or another trusted future system.

## AI Provider Boundary

```text
AIProvider
    ├── FakeAIProvider     deterministic tests and CI
    ├── OpenAIProvider     optional paid live provider
    └── GroqProvider       zero-budget development live provider
```

Provider selection is isolated behind `create_ai_provider`. Retrieval, `DecisionEngine`, `AIProcessingRun`, and WhatsApp transport do not depend on Groq or OpenAI directly.

OpenAI Responses calls keep `store=False`, `background=False`, and `tools=[]`. Groq Responses calls omit unsupported `store`, keep `background=False` and `tools=[]`, and do not send `previous_response_id` or tool definitions. KHLIM Assist does not use provider-side conversation persistence.
