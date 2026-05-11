"""Hybrid retrieval — pgvector cosine + Postgres BM25 + RRF fusion.

Public surface::

    chunks = chunk_search_team(team_id=1, query="why do users bounce?", limit=7)

Retrieval flow:

1. **Dense** — embed the query via :func:`merism.knowledge.embeddings.embed`
   and ORDER BY ``embedding <=> query_vec`` (cosine distance). pgvector
   IVFFLAT index keeps this sub-50ms for <1M chunks.
2. **Lexical** — Postgres ``to_tsvector('simple', content) @@ plainto_tsquery``
   ranked via ``ts_rank_cd``. Backed by a GIN index.
3. **Fuse** — Reciprocal Rank Fusion (k=60, per Cormack et al. 2009):
   ``score = Σ 1/(k + rank_i)`` across both lists. Return the union
   sorted by fused score, trimmed to ``limit``.

Falls back to pure lexical when embeddings are unavailable (API key
missing). Set ``MERISM_KNOWLEDGE_VECTOR_SEARCH=0`` to force lexical.
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.db import connection
from django.db.models import F

from merism.knowledge.embeddings import embed_query
from merism.models import KnowledgeChunk

logger = logging.getLogger(__name__)

_RRF_K = 60


def chunk_search_team(
    *, team_id: int, query: str, limit: int = 7
) -> list[KnowledgeChunk]:
    """Hybrid retrieval across the team's knowledge chunks.

    Returns at most ``limit`` ``KnowledgeChunk`` instances, each with a
    ``distance`` float attribute attached (smaller = more relevant).
    """
    query = query.strip()
    if not query or not team_id:
        return []

    vector_hits: list[tuple[str, float]] = []
    lexical_hits: list[tuple[str, float]] = []

    # Dense branch — skipped when no key / flag off.
    if getattr(settings, "MERISM_KNOWLEDGE_VECTOR_SEARCH", True):
        try:
            vec = embed_query(query)
        except Exception as exc:  # pragma: no cover
            logger.warning("knowledge.search.embed_failed", extra={"error": str(exc)})
            vec = None
        if vec is not None:
            vector_hits = _vector_search(team_id, vec, limit * 2)

    lexical_hits = _lexical_search(team_id, query, limit * 2)

    if not vector_hits and not lexical_hits:
        return []

    chunk_ids = _rrf_merge(vector_hits, lexical_hits, limit=limit)
    # Fetch real rows preserving the fused order.
    chunks = list(
        KnowledgeChunk.objects.filter(id__in=chunk_ids)
        .select_related("document")
        .annotate(fused_order=_preserve_order(chunk_ids))
    )
    chunks.sort(key=lambda c: chunk_ids.index(str(c.id)))
    # Attach distance (from vector list) for citation renderers.
    distance_by_id = {cid: dist for cid, dist in vector_hits}
    for chunk in chunks:
        chunk.distance = distance_by_id.get(str(chunk.id), 0.0)  # type: ignore[attr-defined]
    return chunks


# ── backends ──────────────────────────────────────────────


def _vector_search(team_id: int, vec: list[float], limit: int) -> list[tuple[str, float]]:
    """Return ``[(chunk_id, distance), ...]`` sorted by pgvector cosine."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id::text, (embedding <=> %s::vector) AS distance
            FROM merism_knowledge_chunk
            WHERE team_id = %s AND embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            [vec, team_id, vec, limit],
        )
        return [(row[0], float(row[1])) for row in cursor.fetchall()]


def _lexical_search(team_id: int, query: str, limit: int) -> list[tuple[str, float]]:
    """Return ``[(chunk_id, rank), ...]`` sorted by Postgres ts_rank_cd."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id::text, ts_rank_cd(to_tsvector('simple', content),
                                        plainto_tsquery('simple', %s)) AS rank
            FROM merism_knowledge_chunk
            WHERE team_id = %s
              AND to_tsvector('simple', content) @@ plainto_tsquery('simple', %s)
            ORDER BY rank DESC
            LIMIT %s
            """,
            [query, team_id, query, limit],
        )
        return [(row[0], float(row[1])) for row in cursor.fetchall()]


def _rrf_merge(
    vector_hits: list[tuple[str, float]],
    lexical_hits: list[tuple[str, float]],
    *,
    limit: int,
) -> list[str]:
    """Reciprocal Rank Fusion. Returns chunk_id list sorted by fused score."""
    scores: dict[str, float] = {}
    for rank, (cid, _d) in enumerate(vector_hits):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (_RRF_K + rank + 1)
    for rank, (cid, _d) in enumerate(lexical_hits):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (_RRF_K + rank + 1)
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [cid for cid, _ in ordered[:limit]]


def _preserve_order(ids: list[str]) -> Any:
    # Placeholder for future ORDER-BY-array support; currently unused but
    # kept so the callsite annotation stays readable.
    return F("id")
