"""LLM client factory.

Returns an OpenAI-compatible client using the team's ServiceSettings
(Dograh-style registry + factory). Falls back to env-var config
(MERISM_LLM_API_KEY / MERISM_LLM_BASE_URL) when no team settings exist.

For tests, use :class:`merism.testing.fakes.DeterministicLLM`.
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
    """Raised when no LLM is configured (neither ServiceSettings nor env var)."""


def get_llm(*, async_: bool = False, team: Any = None, base_url: str | None = None) -> Any:
    """Return an OpenAI-compatible client.

    Resolution order:
    1. Team's ServiceSettings (if team provided and configured)
    2. Env-var fallback (MERISM_LLM_API_KEY + MERISM_LLM_BASE_URL)
    """
    if team:
        client = _from_service_settings(team, async_=async_)
        if client:
            return client

    # Env-var fallback
    key = _require_api_key()
    url = base_url or getattr(settings, "MERISM_LLM_BASE_URL", "https://api.deepseek.com")
    if async_:
        return _build_async_client(key, url)
    return _build_sync_client(key, url)


def default_model(team: Any = None) -> str:
    """Return the configured model name."""
    if team:
        config = _get_llm_config(team)
        if config:
            return config.model
    return getattr(settings, "MERISM_LLM_MODEL", "deepseek-chat")


def reasoner_model() -> str:
    return getattr(settings, "MERISM_LLM_REASONER_MODEL", "deepseek-reasoner")


def _from_service_settings(team: Any, *, async_: bool) -> Any | None:
    """Try to build client from team's ServiceSettings."""
    from merism.services.configuration.factory import create_llm_service

    config = _get_llm_config(team)
    if not config:
        return None
    return create_llm_service(config, async_=async_)


def _get_llm_config(team: Any) -> Any | None:
    """Load LLM config from ServiceSettings, or None."""
    from merism.models.service_settings import ServiceSettings

    try:
        ss = ServiceSettings.objects.get(team=team)
        return ss.get_llm_config()
    except ServiceSettings.DoesNotExist:
        return None


def _require_api_key() -> str:
    key = getattr(settings, "MERISM_LLM_API_KEY", "") or os.environ.get("MERISM_LLM_API_KEY", "")
    if not key:
        raise LLMUnavailableError(
            "No LLM configured. Either set up ServiceSettings for the team "
            "or set MERISM_LLM_API_KEY. For tests, use merism.testing.fakes.DeterministicLLM."
        )
    return key


@lru_cache(maxsize=4)
def _build_sync_client(api_key: str, base_url: str) -> Any:
    if OpenAI is None:
        raise ImportError("openai is not installed; run `uv sync --extra dev`.")
    return OpenAI(api_key=api_key, base_url=base_url)


@lru_cache(maxsize=4)
def _build_async_client(api_key: str, base_url: str) -> Any:
    if AsyncOpenAI is None:
        raise ImportError("openai is not installed; run `uv sync --extra dev`.")
    return AsyncOpenAI(api_key=api_key, base_url=base_url)
