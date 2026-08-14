# Phase 1 Acceptance Checklist

## Automated

- [x] webhook GET verification tests pass
- [x] signature validation tests pass
- [x] invalid signature is rejected
- [x] inbound text normalization passes
- [x] inbound persistence passes
- [x] duplicate message test passes
- [x] outbound disabled guard passes
- [x] allowlist guard passes
- [x] mocked outbound text send passes
- [x] mocked outbound template send passes
- [x] status tracking passes
- [x] out-of-order status protection passes
- [x] PostgreSQL migration passes
- [x] PostgreSQL persistence passes
- [x] ruff passes
- [x] mypy passes
- [x] pytest passes
- [ ] CI passes
- [x] no secrets in repository
- [x] no real participant PII

## Owner Live Meta Verification

- [ ] Meta webhook verification succeeds
- [ ] inbound real sandbox WhatsApp message received
- [ ] inbound message persisted
- [ ] duplicate behavior confirmed
- [ ] controlled outbound message reaches test number
- [ ] delivery status webhook received
- [ ] outbound disabled switch confirmed
- [ ] recipient allowlist confirmed
- [ ] no automatic AI reply occurs

Manual live Meta gates remain unchecked until the owner verifies them in their Meta sandbox.
