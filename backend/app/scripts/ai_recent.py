import argparse
import asyncio

from sqlalchemy import select

from app.db.models.ai_processing_run import AIProcessingRun
from app.db.models.message import Message
from app.db.session import AsyncSessionLocal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show recent Phase 2 AI analysis runs.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum rows to display.")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    limit = max(1, min(args.limit, 100))
    async with AsyncSessionLocal() as session:
        runs = list(
            await session.scalars(
                select(AIProcessingRun)
                .order_by(AIProcessingRun.created_at.desc())
                .limit(limit)
            )
        )
        for run in runs:
            message = await session.get(Message, run.message_id)
            preview = _preview(message.text_content if message else None)
            intents = ", ".join(_intent_types(run.interpreted_intents)) or "-"
            print(
                "\t".join(
                    [
                        run.created_at.isoformat(),
                        str(run.conversation_id),
                        preview,
                        run.primary_language.value if run.primary_language else "-",
                        intents,
                        run.decision_level.value if run.decision_level else "-",
                        run.knowledge_source or "-",
                        run.processing_status.value,
                        _preview(run.draft_response),
                    ]
                )
            )


def _intent_types(items: list[dict[str, object]]) -> list[str]:
    values: list[str] = []
    for item in items:
        intent_type = item.get("type")
        if isinstance(intent_type, str):
            values.append(intent_type)
    return values


def _preview(value: str | None, limit: int = 80) -> str:
    if not value:
        return "-"
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3]}..."


if __name__ == "__main__":
    asyncio.run(main())
