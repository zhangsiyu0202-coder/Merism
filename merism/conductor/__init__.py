"""Merism interview conductor.

2-node moderator (decide → generate) per PRODUCT.md §5.2 / ``merism-platform``
Req 14. The first call (``coverage_steer``) returns a structured
``ModeratorDecision`` via function calling; the second call streams the
spoken reply token-by-token. Both run sequentially inside one
``stream_turn`` coroutine — no graph, no policy layer, no macro/meso/micro
split.

Public surface:

- :class:`~merism.conductor.state.ExecutionState` — per-session state
- :class:`~merism.conductor.prompts.ModeratorDecision` — function-call schema
- :func:`~merism.conductor.prompts.build_system_prompt` — prompt builder
- :func:`~merism.conductor.moderator.stream_turn` — async streaming runner
- :mod:`~merism.conductor.guide_cursor` — pure guide-traversal helpers
"""

from __future__ import annotations

from merism.conductor.prompts import (
    ModeratorDecision,
    build_system_prompt,
)
from merism.conductor.state import ExecutionState

__all__ = [
    "ExecutionState",
    "ModeratorDecision",
    "build_system_prompt",
    "stream_turn",
]


def __getattr__(name: str):
    if name == "stream_turn":
        from merism.conductor.moderator import stream_turn

        return stream_turn
    raise AttributeError(name)
