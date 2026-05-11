"""Embedding client for knowledge RAG.

Uses the OpenAI-compat API (DeepSeek via base_url). Returns 1536-dim
vectors by default — matches ``merism.models.EMBEDDING_DIM``. For tests,
import :func:`merism.testing.fakes.embeddings.hash_embedding` instead.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "text-embedding-3-small"


def embed_query(text: str, *, model: str | None = None) -> list[float] | None:
    """Embed a single piece of text. Returns ``None`` on error (caller
    should fall back to lexical-only retrieval)."""
    text = text.strip()
    if not text:
        return None
    client = _client()
    if client is None:
        return None
    try:
        response = client.embeddings.create(
            model=model or _DEFAULT_MODEL,
            input=text,
        )
        return list(response.data[0].embedding)
    except Exception as exc:  # pragma: no cover - live API
        logger.warning("knowledge.embed.failed", extra={"error": str(exc)})
        return None


def embed_batch(texts: list[str], *, model: str | None = None) -> list[list[float] | None]:
    """Embed many texts in one API call."""
    if not texts:
        return []
    client = _client()
    if client is None:
        return [None] * len(texts)
    try:
        response = client.embeddings.create(
            model=model or _DEFAULT_MODEL,
            input=texts,
        )
        return [list(item.embedding) for item in response.data]
    except Exception as exc:  # pragma: no cover
        logger.warning("knowledge.embed_batch.failed", extra={"error": str(exc)})
        return [None] * len(texts)


@lru_cache(maxsize=1)
def _client() -> Any | None:
    """Lazy client — returns None if no API key so import is safe in tests."""
    from merism.memai.llm import LLMUnavailableError, get_llm

    try:
        return get_llm(async_=False)
    except (LLMUnavailableError, ImportError):
        return None
