"""Embedding client for knowledge RAG.

Uses the team's ServiceSettings embedding config (Dograh-style).
Falls back to env-var OpenAI-compat client. For tests, import
:func:`merism.testing.fakes.embeddings.hash_embedding` instead.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def embed_query(text: str, *, model: str | None = None, team: Any = None) -> list[float] | None:
    """Embed a single piece of text. Returns ``None`` on error."""
    text = text.strip()
    if not text:
        return None

    client, mdl = _get_client(team, model)
    if client is None:
        return None
    try:
        response = client.embeddings.create(model=mdl, input=text)
        return list(response.data[0].embedding)
    except Exception as exc:
        logger.warning("knowledge.embed.failed", extra={"error": str(exc)})
        return None


def embed_batch(texts: list[str], *, model: str | None = None, team: Any = None) -> list[list[float] | None]:
    """Embed many texts in one API call."""
    if not texts:
        return []

    client, mdl = _get_client(team, model)
    if client is None:
        return [None] * len(texts)
    try:
        response = client.embeddings.create(model=mdl, input=texts)
        return [list(item.embedding) for item in response.data]
    except Exception as exc:
        logger.warning("knowledge.embed_batch.failed", extra={"error": str(exc)})
        return [None] * len(texts)


def _get_client(team: Any, model_override: str | None) -> tuple[Any, str]:
    """Resolve embedding client: ServiceSettings → env-var fallback."""
    if team:
        from merism.models.service_settings import ServiceSettings
        from merism.services.configuration.factory import create_embedding_service

        try:
            ss = ServiceSettings.objects.get(team=team)
            config = ss.get_embedding_config()
            if config:
                client = create_embedding_service(config)
                return client, model_override or config.model
        except ServiceSettings.DoesNotExist:
            pass

    # Fallback to legacy env-var client
    from merism.memai.llm import LLMUnavailableError, get_llm

    try:
        client = get_llm(async_=False)
        return client, model_override or "text-embedding-3-small"
    except (LLMUnavailableError, ImportError):
        return None, ""
