"""Fake RAG retriever for Ask Merism / knowledge-chunk tests.

Swaps in place of ``products.studies.backend.knowledge_rag.chunk_search_team``
(and the ``hybrid_document_search_*`` variants) when the test is about agent
behaviour, not retrieval quality.

Retrieval is deterministic: results are returned in the order they were
registered. Use a scoring callable if you need ranked results instead.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeRetrievedChunk:
    """Minimal shape matching Merism's ``KnowledgeChunk`` for test purposes."""

    id: str
    content: str
    title: str = ""
    source_type: str = "session"
    source_id: str = ""
    distance: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class FakeRAGRetriever:
    """Returns pre-seeded chunks for any query.

    Example::

        retriever = FakeRAGRetriever()
        retriever.seed("chunk-1", "users hate pricing", distance=0.1)
        retriever.seed("chunk-2", "users love onboarding", distance=0.4)

        results = retriever.chunk_search_team(team_id=1, query="pricing", limit=1)
        assert results[0].id == "chunk-1"
        assert retriever.queries == [("team:1", "pricing", 1)]

    Use ``ranker`` to sort by content match instead of seeding order::

        retriever = FakeRAGRetriever(
            ranker=lambda query, chunk: -chunk.content.count(query),
        )
    """

    def __init__(
        self,
        *,
        ranker: Callable[[str, FakeRetrievedChunk], float] | None = None,
    ) -> None:
        self._chunks: list[FakeRetrievedChunk] = []
        self._ranker = ranker
        self.queries: list[tuple[str, str, int]] = []  # (scope, query, limit)

    # ─── Seeding ────────────────────────────────────────────────

    def seed(
        self,
        chunk_id: str,
        content: str,
        *,
        title: str = "",
        source_type: str = "session",
        source_id: str = "",
        distance: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> FakeRetrievedChunk:
        chunk = FakeRetrievedChunk(
            id=chunk_id,
            content=content,
            title=title,
            source_type=source_type,
            source_id=source_id,
            distance=distance,
            metadata=metadata or {},
        )
        self._chunks.append(chunk)
        return chunk

    def seed_many(self, chunks: Iterable[FakeRetrievedChunk]) -> None:
        self._chunks.extend(chunks)

    # ─── Retrieval surface ──────────────────────────────────────

    def chunk_search_team(
        self, team_id: int, query: str, limit: int = 7
    ) -> list[FakeRetrievedChunk]:
        self.queries.append((f"team:{team_id}", query, limit))
        return self._apply(query, limit)

    def hybrid_document_search_team(
        self, team_id: int, query: str, limit: int = 7
    ) -> list[FakeRetrievedChunk]:
        self.queries.append((f"team:{team_id}", query, limit))
        return self._apply(query, limit)

    def hybrid_document_search(
        self, kb: Any, query: str, limit: int = 5
    ) -> list[FakeRetrievedChunk]:
        scope = f"kb:{getattr(kb, 'id', kb)}"
        self.queries.append((scope, query, limit))
        return self._apply(query, limit)

    def search(self, kb: Any, query: str, limit: int = 5) -> list[FakeRetrievedChunk]:
        return self.hybrid_document_search(kb, query, limit)

    # ─── Internals ──────────────────────────────────────────────

    def _apply(self, query: str, limit: int) -> list[FakeRetrievedChunk]:
        chunks = list(self._chunks)
        if self._ranker is not None:
            chunks.sort(key=lambda c: self._ranker(query, c))  # type: ignore[misc]
        return chunks[:limit]
