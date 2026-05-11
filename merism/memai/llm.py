"""LLM client factory.

Returns an OpenAI-compatible client pointed at DeepSeek by default
(per PRODUCT.md §6). Swap to Anthropic / OpenAI via explicit args.

**Langfuse instrumentation (ADR 0001)**: if ``LANGFUSE_PUBLIC_KEY`` is set
in settings, calls made through these clients are automatically traced
(prompt + completion + latency + cost). Without the key, Langfuse import
is a no-op — zero overhead for local dev / tests.

Live calls are gated on ``MERISM_LLM_API_KEY`` being set. Without a key,
:func:`get_llm` raises — tests should use
:class:`merism.testing.fakes.DeterministicLLM` instead.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from django.conf import settings

try:
    from openai import AsyncOpenAI, OpenAI
except ImportError:  # pragma: no cover - dev env
    OpenAI = None  # type: ignore[assignment,misc]
    AsyncOpenAI = None  # type: ignore[assignment,misc]


class LLMUnavailableError(RuntimeError):
    """Raised when ``MERISM_LLM_API_KEY`` isn't configured."""


def _require_api_key() -> str:
    key = getattr(settings, "MERISM_LLM_API_KEY", "") or os.environ.get("MERISM_LLM_API_KEY", "")
    if not key:
        raise LLMUnavailableError(
            "MERISM_LLM_API_KEY is not set. For tests, use "
            "merism.testing.fakes.DeterministicLLM instead of calling get_llm()."
        )
    return key


def _langfuse_enabled() -> bool:
    return bool(getattr(settings, "LANGFUSE_PUBLIC_KEY", ""))


def _wrap_with_langfuse(client: Any) -> Any:
    """If Langfuse is configured, return a traced wrapper; else return as-is.

    Langfuse's OpenAI integration is import-level — it monkey-patches the
    ``openai`` module. Here we just initialise Langfuse once so the patch
    is active before the first real call.
    """
    if not _langfuse_enabled():
        return client
    try:
        from langfuse import Langfuse

        Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
        # Side effect: Langfuse auto-instruments any `openai` client created
        # after its OpenAIClientInstrumentor runs. We don't need to wrap
        # explicitly.
    except ImportError:  # pragma: no cover - dev env
        pass
    return client


@lru_cache(maxsize=4)
def _build_sync_client(api_key: str, base_url: str) -> Any:
    if OpenAI is None:
        raise ImportError("openai is not installed; run `uv sync --extra dev`.")
    return _wrap_with_langfuse(OpenAI(api_key=api_key, base_url=base_url))


@lru_cache(maxsize=4)
def _build_async_client(api_key: str, base_url: str) -> Any:
    if AsyncOpenAI is None:
        raise ImportError("openai is not installed; run `uv sync --extra dev`.")
    return _wrap_with_langfuse(AsyncOpenAI(api_key=api_key, base_url=base_url))


def get_llm(*, async_: bool = False, base_url: str | None = None) -> Any:
    """Return an OpenAI-compatible client configured for DeepSeek (default).

    Override ``base_url`` to point at a different endpoint (e.g., OpenAI's
    official URL for reasoning-heavy evaluations).
    """
    key = _require_api_key()
    url = base_url or getattr(settings, "MERISM_LLM_BASE_URL", "https://api.deepseek.com")
    if async_:
        return _build_async_client(key, url)
    return _build_sync_client(key, url)


def default_model() -> str:
    return getattr(settings, "MERISM_LLM_MODEL", "deepseek-chat")


def reasoner_model() -> str:
    return getattr(settings, "MERISM_LLM_REASONER_MODEL", "deepseek-reasoner")
