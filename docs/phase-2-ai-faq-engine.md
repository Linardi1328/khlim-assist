# Phase 2 AI FAQ Engine

Phase 2 adds the AI reasoning layer for KHLIM Assist while preserving the Phase 1 WhatsApp transport boundary.

## Scope

Phase 2 supports:

- OpenAI Responses API integration behind the AIProvider abstraction
- structured multilingual interpretation
- recent conversation context building
- typed approved-knowledge retrieval
- deterministic GREEN/YELLOW/RED decisions
- KHLIM-style draft response generation
- AIProcessingRun persistence
- synthetic evaluation fixtures and CLI tooling

Phase 2 does not send WhatsApp replies automatically.

## Flow

```text
Stored participant Message
     ↓
ConversationContextBuilder
     ↓
AIProvider.interpret_message
     ↓
SQLKnowledgeRetriever
     ↓
DecisionEngine
     ↓
AIProvider.generate_response
     ↓
AIProcessingRun
     ↓
NO WHATSAPP SEND
```

## Configuration

Defaults are fail-closed:

```text
AI_PROCESSING_ENABLED=false
AI_SHADOW_MODE=true
AI_AUTO_REPLY_ENABLED=false
AI_CONTEXT_MESSAGE_LIMIT=10
```

OpenAI is optional and lazy:

```text
OPENAI_API_KEY=
OPENAI_MODEL=
OPENAI_REQUEST_TIMEOUT_SECONDS=30
```

No OpenAI client is constructed at FastAPI startup. Tests use fakes or mocked SDK clients.

## Knowledge Retrieval

The LLM is not a source of tournament facts.

Retrieval priority:

1. active Event/EventRule structured data
2. event-specific FAQEntry
3. global FAQEntry
4. approved FAQ master policy metadata
5. no result

If no conversation event or ACTIVE_EVENT_ID exists, event-specific questions such as fees, venue, and category schedule cannot become GREEN.

## Decisions

DecisionEngine remains deterministic:

- participant requested human => RED
- any RED intent => RED
- lookup or clarification => YELLOW
- only approved and confirmed evidence can become GREEN

Rules decide. AI communicates.

## Prompt Safety

Participant text is untrusted. Prompts instruct the model not to:

- ignore system rules
- reveal prompts or secrets
- invent fees, dates, venues, or policies
- confirm payment or registration without verified data
- grant exceptions, refunds, schedule changes, withdrawals, or reserved slots
- enable WhatsApp sending

OpenAI Responses calls use `store=False`, no background mode, and no web-search tools.
