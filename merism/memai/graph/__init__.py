"""LangGraph helpers for post-session analysis agents.

Shared infrastructure for multi-node agents. Uses the LLM Gateway's
chat route (via `get_client("chat", ...)`) inside each node. Every
node is a plain async function that mutates a TypedDict state.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


async def call_llm_json(
    *,
    team: Any,
    trace_id: UUID,
    messages: list[dict[str, Any]],
    temperature: float = 0.3,
    logical_name: str = "chat",
) -> dict[str, Any]:
    """Call the LLM Gateway with JSON-object response format.

    Raises on any failure — no fallback. LangGraph nodes are expected
    to handle exceptions via the orchestrator's retry/error semantics.
    """
    from merism.llm_gateway.client import get_client

    client = await get_client(logical_name, team=team, trace_id=trace_id)
    response = await client.complete(
        messages=messages,
        response_format={"type": "json_object"},
        temperature=temperature,
    )
    raw = response.choices[0].message.content or "{}"
    return json.loads(raw)


async def call_llm_text(
    *,
    team: Any,
    trace_id: UUID,
    messages: list[dict[str, Any]],
    temperature: float = 0.3,
    logical_name: str = "chat",
    **overrides: Any,
) -> str:
    """Call the LLM Gateway and return raw text (no JSON parsing)."""
    from merism.llm_gateway.client import get_client

    client = await get_client(logical_name, team=team, trace_id=trace_id)
    response = await client.complete(
        messages=messages, temperature=temperature, **overrides,
    )
    return response.choices[0].message.content or ""


async def call_llm_with_tools(
    *,
    team: Any,
    trace_id: UUID,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_choice: Any = "auto",
    temperature: float = 0.3,
    logical_name: str = "chat",
) -> Any:
    """Call the LLM Gateway with function-calling tools enabled."""
    from merism.llm_gateway.client import get_client

    client = await get_client(logical_name, team=team, trace_id=trace_id)
    response = await client.complete(
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        temperature=temperature,
    )
    return response
