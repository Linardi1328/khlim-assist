import argparse
import asyncio
from uuid import UUID

from app.ai.fake import FakeAIProvider
from app.ai.openai_client import OpenAIProvider
from app.config.settings import get_settings
from app.db.session import AsyncSessionLocal
from app.services.ai_processing import AIProcessingService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process one stored message through Phase 2 AI.")
    parser.add_argument("--message-id", required=True, help="Message UUID to process.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run analysis without committing it.",
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "fake"],
        default="openai",
        help="AI provider to use. fake is deterministic and CI-safe.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    settings = get_settings()
    provider = FakeAIProvider() if args.provider == "fake" else OpenAIProvider(settings)
    service = AIProcessingService(provider=provider, settings=settings)

    async with AsyncSessionLocal() as session:
        run = await service.process_message(
            session,
            UUID(args.message_id),
            dry_run=args.dry_run,
        )

    print(f"Processing status: {run.processing_status.value}")
    print(f"Language: {run.primary_language.value if run.primary_language else '-'}")
    print(f"Language mode: {run.language_mode.value if run.language_mode else '-'}")
    print(f"Intents: {', '.join(_intent_types(run.interpreted_intents)) or '-'}")
    print(f"Decision: {run.decision_level.value if run.decision_level else '-'}")
    print(f"Knowledge: {run.knowledge_source or '-'}")
    print(f"Recommended PIC: {run.recommended_pic_role.value if run.recommended_pic_role else '-'}")
    print(f"Draft: {run.draft_response or '-'}")
    print("Sent to WhatsApp: NO")


def _intent_types(items: list[dict[str, object]]) -> list[str]:
    values: list[str] = []
    for item in items:
        intent_type = item.get("type")
        if isinstance(intent_type, str):
            values.append(intent_type)
    return values


if __name__ == "__main__":
    asyncio.run(main())
