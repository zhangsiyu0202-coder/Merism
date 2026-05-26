"""LangChain ``ChatOpenAI`` factory adapted for DeepSeek json_mode.

Pattern provenance: design.md §0 / pattern 4 + 5. Nodes call ``build_llm()``
inside the function (not at module top), so model / temperature can swap
per call without process restart and tests can mock cleanly.

DeepSeek-specific constraints (locked by Phase 0 spike):

- The default LangChain ``method="json_schema"`` does not work with
  DeepSeek (HTTP 400 ``"This response_format type is unavailable now"``).
  We always use ``method="json_mode"``.
- Prompts that drive ``with_structured_output`` MUST contain the literal
  word ``JSON`` for DeepSeek's safety check (handled in ``prompts.py``).
- Spike result: 50/50 well-formed responses with json_mode + temperature=0,
  median latency 1469ms, p95 1776ms.

Env vars used:
- ``MERISM_LLM_API_KEY``: required (raises if absent at LLM call time).
- ``MERISM_LLM_BASE_URL``: required (DeepSeek OpenAI-compat base URL).
- Per-Configuration env vars (``JUDGE_MODEL``, ``JUDGE_TEMPERATURE``,
  etc.) are consumed via ``Configuration.from_runnable_config()``, not here.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

if TYPE_CHECKING:
    from langchain_core.runnables import Runnable
    from pydantic import BaseModel


class LLMConfigError(RuntimeError):
    """Raised when required env vars (``MERISM_LLM_API_KEY``,
    ``MERISM_LLM_BASE_URL``) are absent. Surfaced by ``build_llm()`` so
    nodes can catch and degrade to a fallback path (Req 25)."""


def build_llm(model: str, *, temperature: float = 0.0) -> ChatOpenAI:
    """Construct a ``ChatOpenAI`` configured for DeepSeek (or any
    OpenAI-compatible endpoint pointed at by ``MERISM_LLM_BASE_URL``).

    Raises :class:`LLMConfigError` when required env vars are missing —
    nodes catch this and fall through to their failure path.
    """
    api_key = os.environ.get("MERISM_LLM_API_KEY")
    if not api_key:
        raise LLMConfigError("MERISM_LLM_API_KEY is not set")
    base_url = os.environ.get("MERISM_LLM_BASE_URL")
    if not base_url:
        raise LLMConfigError("MERISM_LLM_BASE_URL is not set")
    return ChatOpenAI(
        model=model,
        api_key=SecretStr(api_key),
        base_url=base_url,
        temperature=temperature,
    )


def build_evaluator(llm: ChatOpenAI, schema: type[BaseModel]) -> Runnable:
    """Wrap an LLM with structured-output binding for a Pydantic schema.

    ``method="json_mode"`` is non-negotiable for DeepSeek — see module
    docstring. Caller is responsible for ensuring the prompt contains
    the word ``JSON`` (enforced by ``prompts.py`` templates).
    """
    return llm.with_structured_output(schema, method="json_mode")


__all__ = ["LLMConfigError", "build_evaluator", "build_llm"]
