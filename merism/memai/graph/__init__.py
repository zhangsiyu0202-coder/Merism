"""LangGraph helpers for post-session analysis agents.

Shared infrastructure for multi-node agents. Routes through the LLM
gateway (:func:`merism.llm_gateway.client.get_client`) which currently
returns a raw ``openai.AsyncOpenAI`` instance — so we use the OpenAI
SDK's ``chat.completions.create`` API directly.

Each node calls one of these helpers; the returned dict / string / raw
response is the node's contribution to the LangGraph state.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from merism.memai.llm import default_model

logger = logging.getLogger(__name__)


async def call_llm_json(
    *,
    team: Any,
    trace_id: UUID,  # noqa: ARG001 — reserved for future trace bind
    messages: list[dict[str, Any]],
    temperature: float = 0.3,
    logical_name: str = "chat",
) -> dict[str, Any]:
    """Call the LLM with JSON-object response format. Raises on any failure."""
    from merism.llm_gateway.client import get_client

    client = await get_client(logical_name, team=team, trace_id=trace_id)
    completion = await client.chat.completions.create(
        model=default_model(),
        messages=messages,
        response_format={"type": "json_object"},
        temperature=temperature,
    )
    raw = completion.choices[0].message.content or "{}"
    return json.loads(raw)


async def call_llm_text(
    *,
    team: Any,
    trace_id: UUID,  # noqa: ARG001
    messages: list[dict[str, Any]],
    temperature: float = 0.3,
    logical_name: str = "chat",
    **overrides: Any,
) -> str:
    """Call the LLM and return raw text (no JSON parsing)."""
    from merism.llm_gateway.client import get_client

    client = await get_client(logical_name, team=team, trace_id=trace_id)
    completion = await client.chat.completions.create(
        model=default_model(),
        messages=messages,
        temperature=temperature,
        **overrides,
    )
    return completion.choices[0].message.content or ""


async def call_llm_with_tools(
    *,
    team: Any,
    trace_id: UUID,  # noqa: ARG001
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_choice: Any = "auto",
    temperature: float = 0.3,
    logical_name: str = "chat",
) -> Any:
    """Call the LLM with function-calling tools enabled."""
    from merism.llm_gateway.client import get_client

    client = await get_client(logical_name, team=team, trace_id=trace_id)
    completion = await client.chat.completions.create(
        model=default_model(),
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        temperature=temperature,
    )
    return completion
