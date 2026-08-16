# Phase 2.1 Provider Portability

Phase 2.1 adds Groq as a first-class `AIProvider` implementation while preserving OpenAI and the deterministic fake provider.

## Providers

- `groq`: default development live provider for zero-budget evaluation. Initial model is `openai/gpt-oss-120b`.
- `openai`: optional paid live provider.
- `fake`: deterministic local and CI provider only.

Provider selection is isolated behind `create_ai_provider`. Retrieval, policy, persistence, and WhatsApp transport do not depend on Groq.

## Request Boundaries

OpenAI Responses requests use:

```text
store=False
background=False
tools=[]
```

Groq Responses requests:

```text
background=False
tools=[]
```

Groq requests do not send unsupported `store`, do not send `temperature`, do not send `previous_response_id`, and do not enable web search, MCP, code execution, browser tools, or other external tools.

KHLIM Assist does not use provider-side conversation persistence. Drafts are persisted only in application-owned `AIProcessingRun` records.

## Owner Live Groq Evaluation

Do not run live Groq evaluation in CI. Configure locally with owner credentials:

```bash
export AI_PROVIDER="groq"
export GROQ_API_KEY="<OWNER_LOCAL_KEY>"
export GROQ_MODEL="openai/gpt-oss-120b"

export AI_PROCESSING_ENABLED=true
export AI_SHADOW_MODE=true
export AI_AUTO_REPLY_ENABLED=false

python -m app.scripts.ai_eval --provider groq
```

Use the same evaluation corpus as fake/OpenAI checks so provider performance can be compared fairly. The corpus covers English, Mandarin, Bahasa Melayu, mixed Mandarin-English, Manglish, fragmented language, multi-intent questions, prompt injection, missing factual evidence, eligibility exceptions, and payment verification.

## Privacy And Free-Tier Notes

Groq inference does not use application-side conversation persistence through the Responses API. KHLIM does not control Groq infrastructure.

Before using real participant conversations, enable Groq Zero Data Retention in Groq Data Controls. Until then, use synthetic or anonymized test data for owner evaluation.

Development is intended to operate within Groq's current free-tier limits. Do not encode provider rate limits into business logic; provider 429s surface as `AIProviderRateLimitError`.

## Safety Boundary

Rules decide. AI communicates.

Groq may classify participant language and draft KHLIM-style responses, but approved facts must come from `KnowledgeResult` and deterministic `DecisionResult`. Phase 2.1 does not enable automatic WhatsApp replies.
