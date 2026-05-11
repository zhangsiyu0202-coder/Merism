"""Thin LiteLLM wrapper for HTTP-protocol providers.

All retry, fallback, cost calculation, and provider-specific quirks are
delegated to LiteLLM. This module only adds:

1. Credential decryption from ``LLMProvider.credentials_encrypted``
2. Langfuse ``@observe`` tracing (when Langfuse keys are configured)
3. Metadata injection (team_id, trace_id, logical_name)

Usage (via :func:`merism.llm_gateway.client.get_client`)::

    client = await get_client("chat", team=team, trace_id=trace_id)
    async for chunk in client.stream(messages=[...]):
        print(chunk.choices[0].delta.content)
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import litellm

try:
    from langfuse.decorators import observe
except ImportError:
    try:
        from langfuse import observe
    except ImportError:
        # Langfuse not installed or not configured — @observe becomes a no-op.
        def observe(**_kwargs):  # type: ignore[no-redef]
            def _decorator(fn):
                return fn
            return _decorator

from merism.models.llm_gateway import LLMProvider, LLMRoute
from merism.recruitment.crypto import decrypt_credentials

logger = logging.getLogger(__name__)

# Suppress LiteLLM's verbose default logging (it logs every request at INFO).
litellm.suppress_debug_info = True


class LiteLLMClient:
    """HTTP LLM client backed by LiteLLM.

    Instantiated by :func:`merism.llm_gateway.client.get_client` — not
    directly by business code.
    """

    def __init__(
        self,
        provider: LLMProvider,
        route: LLMRoute,
        *,
        trace_id: UUID,
        fallback_provider: LLMProvider | None = None,
    ) -> None:
        self.provider = provider
        self.route = route
        self.trace_id = trace_id
        self.fallback_provider = fallback_provider

        self._api_key = decrypt_credentials(provider.credentials_encrypted)["api_key"]
        self._fallback_api_key = (
            decrypt_credentials(fallback_provider.credentials_encrypted)["api_key"] if fallback_provider else None
        )

    def _base_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.provider.model,
            "api_base": self.provider.base_url,
            "api_key": self._api_key,
            "timeout": self.route.timeout_seconds,
            "num_retries": self.route.max_retries,
            "metadata": {
                "team_id": str(self.route.team_id),
                "trace_id": str(self.trace_id),
                "logical_name": self.route.logical_name,
            },
        }
        if self.provider.extra_headers:
            kwargs["extra_headers"] = self.provider.extra_headers
        if self.route.max_output_tokens:
            kwargs["max_tokens"] = self.route.max_output_tokens
        # LiteLLM fallback: list of model dicts
        if self.fallback_provider and self._fallback_api_key:
            kwargs["fallbacks"] = [
                {
                    "model": self.fallback_provider.model,
                    "api_base": self.fallback_provider.base_url,
                    "api_key": self._fallback_api_key,
                }
            ]
        return kwargs

    @observe(as_type="generation")
    async def complete(self, messages: list[dict[str, Any]], **overrides: Any) -> Any:
        """Non-streaming completion. Returns full LiteLLM ModelResponse."""
        kwargs = {**self._base_kwargs(), "messages": messages, "stream": False, **overrides}
        if "temperature" not in overrides:
            kwargs["temperature"] = self.route.temperature
        return await litellm.acompletion(**kwargs)

    def sync_complete(self, messages: list[dict[str, Any]], **overrides: Any) -> Any:
        """Synchronous non-streaming completion."""
        kwargs = {**self._base_kwargs(), "messages": messages, "stream": False, **overrides}
        if "temperature" not in overrides:
            kwargs["temperature"] = self.route.temperature
        return litellm.completion(**kwargs)

    def sync_stream(self, messages: list[dict[str, Any]], **overrides: Any) -> Any:
        """Synchronous streaming completion. Returns an iterator."""
        kwargs = {**self._base_kwargs(), "messages": messages, "stream": True, **overrides}
        if "temperature" not in overrides:
            kwargs["temperature"] = self.route.temperature
        return litellm.completion(**kwargs)

    def sync_embed(self, texts: list[str], **overrides: Any) -> Any:
        """Synchronous embedding call."""
        kwargs = {
            "model": self.provider.model,
            "api_base": self.provider.base_url,
            "api_key": self._api_key,
            "input": texts,
            "timeout": self.route.timeout_seconds,
            **overrides,
        }
        return litellm.embedding(**kwargs)

    @observe(as_type="generation")
    async def stream(self, messages: list[dict[str, Any]], **overrides: Any) -> AsyncIterator[Any]:
        """Streaming completion. Yields LiteLLM chunk objects."""
        kwargs = {**self._base_kwargs(), "messages": messages, "stream": True, **overrides}
        if "temperature" not in overrides:
            kwargs["temperature"] = self.route.temperature
        response = await litellm.acompletion(**kwargs)
        async for chunk in response:
            yield chunk

    @observe(as_type="generation")
    async def embed(self, texts: list[str], **overrides: Any) -> Any:
        """Embedding call. Returns LiteLLM EmbeddingResponse."""
        kwargs = {
            "model": self.provider.model,
            "api_base": self.provider.base_url,
            "api_key": self._api_key,
            "input": texts,
            "timeout": self.route.timeout_seconds,
            **overrides,
        }
        return await litellm.aembedding(**kwargs)


__all__ = ["LiteLLMClient"]
