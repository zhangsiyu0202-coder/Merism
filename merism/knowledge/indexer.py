"""Session quote indexer — pipes quotes into the RAG index.

For each new ``SessionQuote`` we:
1. Ensure a ``KnowledgeDocument`` (``source_type=session_insight``)
   exists for the parent session.
2. Embed the quote text (sync, via :mod:`merism.knowledge.embeddings`).
3. Write a ``KnowledgeChunk`` row with the embedding + metadata
   (``study_id``, ``session_id``, ``quote_id``, ``question_id``,
   ``concept_id``, ``tags``).
4. Mark the quote's ``embedded_at`` so we don't reindex.

Hybrid search (BM25 + cosine) already runs over chunks; Ask Merism and
Study Report generation automatically get quote retrieval once rows
land here.

The indexer uses sync DB / embedding calls wrapped in ``sync_to_async``
to stay compatible with the async Celery task flow.
"""

from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import sync_to_async
from django.utils import timezone

from merism.knowledge.embeddings import embed_batch
from merism.models import (
    InterviewSession,
    KnowledgeChunk,
    KnowledgeDocument,
    SessionQuote,
)

logger = logging.getLogger(__name__)


async def index_session_quotes(
    session: InterviewSession,
    quotes: list[SessionQuote],
) -> int:
    """Index a session's quotes into KnowledgeChunk. Returns the number
    of new chunk rows written.

    Idempotent per-quote via ``SessionQuote.embedded_at``.
    """
    pending = [q for q in quotes if q.embedded_at is None and q.text.strip()]
    if not pending:
        return 0

    document = await _get_or_create_document(session)

    # Batched embedding — one API call for all pending quotes.
    texts = [q.text for q in pending]
    embeddings = await sync_to_async(embed_batch)(texts)

    # Write chunks; skip any quote whose embedding failed (fallback=None).
    written = await _persist_chunks(pending, embeddings, document)
    if written:
        now = timezone.now()
        await _mark_embedded(pending, now)
    logger.info(
        "knowledge.index_session_quotes.done",
        extra={"session_id": str(session.id), "count": written},
    )
    return written


# ── DB + indexing helpers ──

@sync_to_async
def _get_or_create_document(session: InterviewSession) -> KnowledgeDocument:
    doc, _created = KnowledgeDocument.objects.get_or_create(
        team=session.team,
        study=session.study,
        session=session,
        source_type=KnowledgeDocument.SourceType.SESSION_INSIGHT,
        defaults={
            "title": f"Session {str(session.id)[:8]} quotes",
            "content": "",
            "status": KnowledgeDocument.Status.INDEXED,
            "metadata": {"kind": "session_quotes"},
        },
    )
    return doc


@sync_to_async
def _persist_chunks(
    quotes: list[SessionQuote],
    embeddings: list[list[float] | None],
    document: KnowledgeDocument,
) -> int:
    """Write one KnowledgeChunk row per quote. Chunk_index is assigned
    to avoid colliding with existing chunks on this document.
    """
    base = KnowledgeChunk.objects.filter(document=document).count()
    created = 0
    for offset, (quote, embedding) in enumerate(zip(quotes, embeddings, strict=False)):
        if embedding is None:
            # Embedding failed — skip this quote; we'll retry on next run.
            continue
        KnowledgeChunk.objects.create(
            team=quote.team,
            document=document,
            chunk_index=base + offset,
            content=quote.text,
            embedding=embedding,
            metadata={
                "quote_id": str(quote.id),
                "session_id": str(quote.session_id),
                "study_id": str(quote.study_id),
                "question_id": quote.question_id or None,
                "concept_id": quote.concept_id or None,
                "ts_start_ms": quote.ts_start_ms,
                "ts_end_ms": quote.ts_end_ms,
                "importance": quote.importance,
                "tags": quote.tags,
            },
        )
        created += 1
    return created


@sync_to_async
def _mark_embedded(quotes: list[SessionQuote], when: Any) -> None:
    ids = [q.id for q in quotes]
    SessionQuote.objects.filter(id__in=ids).update(embedded_at=when)
