# Phase 0 Acceptance Checklist

## Verified

- [x] FastAPI app starts
- [x] PostgreSQL connection works
- [x] migrations work
- [x] health endpoint works
- [x] schemas validate
- [x] models persist
- [x] WhatsApp webhook parser works with fixtures
- [x] no live replies are sent
- [x] knowledge files validate
- [x] FAQ taxonomy exists
- [x] response style exists
- [x] escalation policy exists
- [x] decision engine passes tests
- [x] PIC routing passes tests
- [x] evaluation cases validate
- [x] English examples exist
- [x] Malay examples exist
- [x] Mandarin examples exist
- [x] mixed-language examples exist
- [x] multi-intent examples exist
- [x] clarification examples exist
- [x] escalation examples exist
- [x] no real participant PII exists
- [x] `.env` is ignored
- [x] no credentials exist in source
- [x] `pytest` passes
- [x] `ruff` passes
- [x] `mypy` passes
- [x] README is complete

## Verification Commands

```bash
POSTGRES_SMOKE_DATABASE_URL=postgresql+asyncpg://khlim_assist@localhost:5433/khlim_assist pytest
ruff check .
mypy backend/app
DATABASE_URL=postgresql+asyncpg://khlim_assist@localhost:5433/khlim_assist alembic upgrade head
```

## Verified Results

- `pytest`: 47 passed with PostgreSQL smoke tests enabled.
- `ruff check .`: passed.
- `mypy backend/app`: passed.
- `alembic upgrade head`: passed against PostgreSQL.
- PostgreSQL smoke path: connection, migration, Event persistence, and Handoff persistence passed.
- Secret/PII scan: no matching credential or long numeric identifier patterns found in source files.
