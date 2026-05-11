"""Merism knowledge / RAG layer.

Public surface:

- :func:`merism.knowledge.citations.format_chunk_citations` — format chunks
  into citation dicts for Ask Merism / Custom Report answers.
- :func:`merism.knowledge.search.chunk_search_team` — hybrid BM25 + pgvector
  retrieval.
- :func:`merism.knowledge.embeddings.embed_query` / ``embed_batch`` — DeepSeek
  embedding client.

No HogQL. No ClickHouse. Postgres + pgvector only.
"""

from __future__ import annotations

from merism.knowledge.citations import format_chunk_citations
from merism.knowledge.embeddings import embed_batch, embed_query
from merism.knowledge.search import chunk_search_team

__all__ = [
    "chunk_search_team",
    "embed_batch",
    "embed_query",
    "format_chunk_citations",
]
