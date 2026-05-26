"""LangGraph runtime state for the v3 conductor.

State decomposition follows Google's `gemini-fullstack-langgraph-quickstart`
pattern: split TypedDicts by node-output concern, keep one ``OverallState``
as the union, and use ``Annotated[list, operator.add]`` reducers so nodes
return only their incremental contribution rather than the full list.

Per docs/specs/conductor-v3/design.md §3. ``total=False`` everywhere — node
returns are partial dicts that LangGraph merges into the running state.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from merism.conductor.schema import Turn

#: Three follow-up modes selected by the participant or moderator at session
#: start. ``off`` → engine never calls the judge LLM between turns;
#: ``standard`` → lenient sufficiency bar with the configured ``max_followups``
#: budget; ``deep`` → strict bar with budget multiplied by
#: ``Configuration.deep_followups_multiplier``.
FollowUpMode = Literal["off", "standard", "deep"]


class OverallState(TypedDict, total=False):
    """The union of every field any v3 node may read or write.

    Lifecycle:

    - **Set by runner at session start**: ``outline``, ``follow_up_mode``,
      ``section_i``, ``question_i``, ``probe_count``, ``transcript`` (initial
      empty list), ``done``.
    - **Updated by ``ask_and_wait``**: ``last_answer``, ``transcript``
      (appends a single :class:`~merism.conductor.schema.Turn` via the
      ``operator.add`` reducer — return only the new turn).
    - **Updated by judge nodes**: ``pending_probe``, ``probe_count``,
      ``last_evaluation``, ``last_error``.
    - **Updated by ``advance_cursor``**: ``section_i``, ``question_i``,
      ``probe_count``, ``done``.
    """

    # ── input (set by runner) ────────────────────────────────────────────
    outline: dict[str, Any]  # Outline.model_dump() — TypedDict can't carry Pydantic directly
    follow_up_mode: FollowUpMode

    # ── cursor ───────────────────────────────────────────────────────────
    section_i: int
    question_i: int
    probe_count: int

    # ── per-turn (ask + judge_*) ─────────────────────────────────────────
    pending_probe: str | None
    last_answer: str
    last_evaluation: dict[str, Any] | None

    # ── transcript: each node returns [new_turn]; reducer appends ────────
    transcript: Annotated[list[Turn], operator.add]

    # ── terminal ─────────────────────────────────────────────────────────
    done: bool
    last_error: str | None


class JudgeOutput(TypedDict, total=False):
    """Partial state update returned by a judge node.

    Each judge node returns only the keys it touches. LangGraph merges the
    partial dict into ``OverallState`` automatically.
    """

    pending_probe: str | None
    probe_count: int
    last_evaluation: dict[str, Any]
    last_error: str | None


class AdvanceOutput(TypedDict, total=False):
    """Partial state update returned by ``advance_cursor``."""

    section_i: int
    question_i: int
    pending_probe: None
    probe_count: int
    done: bool


__all__ = ["AdvanceOutput", "FollowUpMode", "JudgeOutput", "OverallState"]
