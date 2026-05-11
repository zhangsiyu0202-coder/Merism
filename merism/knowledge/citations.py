"""Chunk citation formatting.

Pure function with no DB imports — mirrors the shape Ask Merism and Custom
Report sidebars expect for the ``citations`` field of an answer payload.

Accepts any object that quacks like a ``KnowledgeChunk``:
  - ``chunk.id``, ``chunk.content``, ``chunk.distance``
  - ``chunk.source_document`` with ``.id``, ``.title``, ``.source_type``, ``.source_id``

Produced by :func:`merism.knowledge.search.hybrid_search` etc.; test factories
in ``merism.testing.factories.knowledge.make_knowledge_chunk`` match this shape.
"""

from __future__ import annotations

from typing import Any


_EXCERPT_MAX_CHARS = 280


def format_chunk_citations(chunks: list[Any], start_no: int = 1) -> list[dict[str, Any]]:
    """Convert ranked chunks into citation dicts for the SSE ``done`` payload.

    Each entry includes document-level keys plus chunk-level additions
    (``chunkId``, ``excerpt`` ≤ 280 chars, ``cosine``).
    """
    citations: list[dict[str, Any]] = []
    for i, chunk in enumerate(chunks, start_no):
        doc = getattr(chunk, "source_document", None) or getattr(chunk, "document", None)
        excerpt = (getattr(chunk, "content", "") or "")[:_EXCERPT_MAX_CHARS]
        cosine = float(getattr(chunk, "distance", 0.0))
        citations.append(
            {
                "docNo": i,
                "documentId": str(doc.id) if doc else "",
                "title": getattr(doc, "title", "") if doc else "",
                "sourceType": getattr(doc, "source_type", "") if doc else "",
                "sourceId": getattr(doc, "source_id", "") if doc else "",
                "chunkId": str(chunk.id),
                "excerpt": excerpt,
                "cosine": cosine,
            }
        )
    return citations
