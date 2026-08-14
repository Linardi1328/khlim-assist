# Phase 2 Acceptance Checklist

## Automated

- [x] OpenAI provider abstraction tests pass
- [x] Structured interpretation schema passes
- [x] multilingual interpretation tests pass
- [x] multi-intent tests pass
- [x] context builder tests pass
- [x] knowledge retrieval tests pass
- [x] factual knowledge-topic schema tests pass
- [x] exact FAQ retrieval collision tests pass
- [x] deterministic EventRule selection tests pass
- [x] active event scoping tests pass
- [x] no-knowledge fallback tests pass
- [x] DecisionEngine integration tests pass
- [x] GREEN evidence requirements pass
- [x] YELLOW clarification tests pass
- [x] YELLOW lookup tests pass
- [x] RED authority tests pass
- [x] response style tests pass
- [x] prompt injection tests pass
- [x] participant-only AI processing guard tests pass
- [x] strict structured-output request tests pass
- [x] no auto WhatsApp send test passes
- [x] AI failure does not break WhatsApp ingestion
- [x] AIProcessingRun persistence passes
- [x] PostgreSQL migration passes
- [x] PostgreSQL integration tests pass
- [x] evaluation fixture tests pass
- [x] ruff passes
- [x] mypy passes
- [x] pytest passes
- [x] CI passes
- [x] no real participant PII
- [x] no secrets

## Owner / Live OpenAI

- [ ] API key configured locally
- [ ] supported model configured
- [ ] English interpretation works
- [ ] Mandarin interpretation works
- [ ] Malay interpretation works
- [ ] mixed-language interpretation works
- [ ] multi-intent interpretation works
- [ ] approved FAQ draft is correct
- [ ] unsupported fact is not invented
- [ ] eligibility exception is RED
- [ ] payment verification is YELLOW
- [ ] no WhatsApp auto-message is sent

Owner live OpenAI gates must remain unchecked until genuinely performed by the owner.
