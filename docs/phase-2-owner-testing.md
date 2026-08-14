# Phase 2 Owner Testing

Separate automated verification from optional live OpenAI verification.

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
- deterministic evaluation prints structured metrics
- no WhatsApp message is sent by AI processing

## Live OpenAI Verification

This does not require live WhatsApp.

Configure local environment:

```bash
export DATABASE_URL="postgresql+asyncpg://khlim_assist@localhost:5433/khlim_assist"
export OPENAI_API_KEY="<OWNER_OPENAI_API_KEY>"
export OPENAI_MODEL="<SUPPORTED_MODEL_ID>"
export AI_PROCESSING_ENABLED=true
export AI_SHADOW_MODE=true
export AI_AUTO_REPLY_ENABLED=false
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

Inspect recent analyses:

```bash
python -m app.scripts.ai_recent --limit 10
```

Run optional live OpenAI structured eval:

```bash
python -m app.scripts.ai_eval --provider openai
```

Report actual metrics. Do not claim production accuracy from synthetic fixtures.

## Suggested Live OpenAI Prompts

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

Live OpenAI owner gates remain unchecked until the owner performs them.
