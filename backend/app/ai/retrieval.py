from typing import Protocol


class KnowledgeRetriever(Protocol):
    async def retrieve(self, query: str, event_id: str | None = None) -> list[str]:
        """Return trusted knowledge snippets for the interpreted participant request."""


class EmptyKnowledgeRetriever:
    async def retrieve(self, query: str, event_id: str | None = None) -> list[str]:
        return []
