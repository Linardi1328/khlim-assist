# Phase 2 human-review draft regression

Live owner testing found that Groq could generate an unverified operational promise such as "I'll forward your request and get back to you" for a RED decision even though Phase 2 does not perform handoffs.

The runtime boundary is now deterministic: when `DecisionResult.requires_human` is true, `ResponseGenerator` returns a fixed acknowledgement and does not call the provider for draft generation. Unit coverage lives in `backend/tests/unit/test_ai_responder.py`.
