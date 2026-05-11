"""Quote embedder — turns SessionQuote rows into vectors.

Strategy: re-use the existing KnowledgeChunk indexing path. After
``merism.knowledge.indexer.index_session_quotes`` runs, every quote
has a corresponding chunk with an embedding in
``KnowledgeChunk.embedding`` (keyed by ``metadata["quote_id"]``).

The themes pipeline just needs a helper that returns
``list[(quote_id, embedding_vector)]`` for all quotes in a study. We
DON'T write new embeddings here; we read from the existing chunk table.

If an embedding is missing (embedded_at IS NULL), we log and skip — the
clusterer will just have fewer samples that pass.
"""

from __future__ import annotations

import logging
from uuid import UUID

from asgiref.sync import sync_to_async

from merism.models import KnowledgeChunk, SessionQuote, Study

logger = logging.getLogger(__name__)


@sync_to_async
def fetch_study_quote_embeddings(study_id: str | UUID) -> list[dict]:
    """Return list of {quote_id, session_id, text, embedding} for the study.

    Only includes quotes that have been embedded (``embedded_at IS NOT NULL``).
    The embedding comes from the matching KnowledgeChunk row (via metadata).
    """
    return _fetch_sync(study_id)


def _fetch_sync(study_id: str | UUID) -> list[dict]:
    quotes = list(
        SessionQuote.objects.filter(
            study_id=study_id, embedded_at__isnull=False
        ).values("id", "session_id", "text")
    )
    if not quotes:
        return []

    # Fetch chunks by quote_id (stored in metadata). Because SQLite in tests
    # doesn't support the pgvector JSON-path operators, we iterate on the
    # app side.
    quote_ids = {str(q["id"]) for q in quotes}
    chunks = KnowledgeChunk.objects.filter(
        team__studies__id=study_id,
    ).only("embedding", "metadata")

    chunk_by_quote: dict[str, list[float]] = {}
    for c in chunks:
        qid = (c.metadata or {}).get("quote_id")
        if qid in quote_ids and c.embedding is not None:
            # pgvector returns list-like; coerce to list[float]
            chunk_by_quote[qid] = list(c.embedding)

    results: list[dict] = []
    for q in quotes:
        emb = chunk_by_quote.get(str(q["id"]))
        if emb is None:
            continue
        results.append(
            {
                "quote_id": str(q["id"]),
                "session_id": str(q["session_id"]),
                "text": q["text"],
                "embedding": emb,
            }
        )

    logger.info(
        "themes.embedder.fetched",
        extra={"study_id": str(study_id), "count": len(results)},
    )
    return results


async def ensure_quotes_embedded(study_id: str | UUID) -> int:
    """Trigger embedding for any quotes in the study that are not yet
    embedded. Returns how many were newly embedded.

    This is a safety net in case a session landed before the indexer ran
    (or the embedding failed previously). Usually a no-op.
    """
    from merism.knowledge.indexer import index_session_quotes

    @sync_to_async
    def _pending_sessions() -> list[UUID]:
        return list(
            SessionQuote.objects.filter(
                study_id=study_id, embedded_at__isnull=True
            ).values_list("session_id", flat=True).distinct()
        )

    sessions = await _pending_sessions()
    if not sessions:
        return 0

    from merism.models import InterviewSession

    total = 0
    for session_id in sessions:
        try:
            session = await sync_to_async(
                lambda: InterviewSession.objects.select_related("team", "study").get(id=session_id)
            )()
            quotes = await sync_to_async(
                lambda: list(SessionQuote.objects.filter(session_id=session_id, embedded_at__isnull=True))
            )()
            total += await index_session_quotes(session, quotes)
        except Exception:
            logger.exception(
                "themes.embedder.backfill_failed",
                extra={"study_id": str(study_id), "session_id": str(session_id)},
            )
    return total
