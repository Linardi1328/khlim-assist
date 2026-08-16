# Phase 2 Owner Testing

Separate automated verification from optional live provider verification. For environment parity with CI, owner live testing should ideally use Python 3.12.

## Automated Verification

```bash
python -m pip install -e ".[dev]"
docker compose up -d db
ruff check .
mypy backend/app
pytest
DATABASE_URL="postgresql+asyncpg://khlim_assist@localhost:5433/khlim_assist" alembic upgrade head
POSTGRES_SMOKE_DATABASE_URL="postgresql+asyncpg://khlim_assist@localhost:5433/khlim_assist" pytest
python -m app.scripts.ai_eval --provider fake
```

Expected:

- tests pass without Meta credentials
- tests pass without OpenAI credentials
- tests pass without Groq credentials
- deterministic evaluation prints structured metrics
- no WhatsApp message is sent by AI processing
- human-required decisions use deterministic acknowledgement drafts and never claim that a PIC was contacted, a request was forwarded, or a follow-up was scheduled

## Live Groq Verification

This does not require live WhatsApp. Use synthetic or anonymized messages until Groq Zero Data Retention is enabled in Groq Data Controls.

Configure local environment:

```bash
export AI_PROVIDER="groq"
export GROQ_API_KEY="<OWNER_LOCAL_KEY>"
export GROQ_MODEL="openai/gpt-oss-120b"
export AI_PROCESSING_ENABLED=true
export AI_SHADOW_MODE=true
export AI_AUTO_REPLY_ENABLED=false
export WHATSAPP_OUTBOUND_ENABLED=false
```

### Required Phase 2.1 owner-live compatibility smoke

Run the representative live subset:

```bash
python -m app.scripts.ai_eval --provider groq --owner-smoke
```

The owner-smoke mode uses six existing synthetic evaluation cases covering GREEN, YELLOW, RED, multilingual, mixed/multi-intent, clarification, and high-risk routing behavior. For Groq it defaults to a conservative 30-second delay between cases to reduce free-tier rate-limit pressure. The CLI prints per-case progress so a slow or rate-limited request is visible.

Expected:

- all six requests reach Groq successfully
- no JSON-schema compatibility error occurs
- structured metrics are printed after the six cases complete
- a provider 429 is reported as an incomplete owner gate, not as a passing result
- no WhatsApp message is sent

If the account still reaches a rate limit, inspect the account limits and rerun later with a larger explicit delay, for example:

```bash
python -m app.scripts.ai_eval --provider groq --owner-smoke --delay-seconds 45
```

Do not claim the owner-live compatibility gate passed unless the smoke command completes and prints metrics.

### Full-corpus live Groq quality benchmark

The full corpus remains available for provider-quality benchmarking:

```bash
python -m app.scripts.ai_eval --provider groq --delay-seconds 30
```

This can take many minutes on a free-tier account and may still hit organization-level request or token limits depending on recent usage. It is required before claiming full-corpus Groq quality approval, but it is separate from the Phase 2.1 shadow-only provider compatibility smoke. Do not enable automatic replies based on a smoke result.

Report actual metrics. Do not claim production accuracy from synthetic fixtures.

## Live OpenAI Verification

This does not require live WhatsApp.

Configure local environment:

```bash
export DATABASE_URL="postgresql+asyncpg://khlim_assist@localhost:5433/khlim_assist"
export AI_PROVIDER="openai"
export OPENAI_API_KEY="<OWNER_OPENAI_API_KEY>"
export OPENAI_MODEL="<SUPPORTED_MODEL_ID>"
export AI_PROCESSING_ENABLED=true
export AI_SHADOW_MODE=true
export AI_AUTO_REPLY_ENABLED=false
export WHATSAPP_OUTBOUND_ENABLED=false
```

Run the API or create local synthetic messages through a test fixture/script. Then process one stored message:

```bash
python -m app.scripts.ai_process_message --message-id "<MESSAGE_UUID>"
```

Expected output includes:

```text
Processing status: COMPLETED
Decision: GREEN / YELLOW / RED
Draft: <stored draft>
Sent to WhatsApp: NO
```

For RED/human-required decisions, the draft must be a deterministic acknowledgement that says review is needed without claiming that a handoff, forwarding action, or future follow-up has already been initiated.

Inspect recent analyses:

```bash
python -m app.scripts.ai_recent --limit 10
```

Run optional live OpenAI structured eval:

```bash
python -m app.scripts.ai_eval --provider openai
```

Report actual metrics. Do not claim production accuracy from synthetic fixtures.

## Suggested Live Provider Prompts

- `Where do I register?`
- `U16 still got slot ah?`
- `coach 2012 可以打 u16 吗`
- `外国人可以参加吗？`
- `Pendaftaran masih buka ke?`
- `Can my overage player make exception?`
- `Have you received my payment?`
- `U16 Sunday? max 4 and foreigner can join?`

Expected:

- approved facts are used only when evidence exists
- payment/registration status remains YELLOW lookup
- exceptions/refunds/reserved slots remain RED
- prompt-injection attempts do not alter approved facts
- no WhatsApp auto-message is sent

Live provider owner gates remain unchecked until the owner performs them.
