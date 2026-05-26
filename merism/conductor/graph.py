"""LangGraph ``StateGraph`` wiring for the v3 conductor.

Pattern provenance: design.md §0 / pattern 9 reversed. Google compiles
without a checkpointer and lets LangGraph Cloud inject one at runtime;
we self-host on Django and so wire the checkpointer at compile time
via :func:`build_graph` (see also ``text_adapter.get_graph`` for the
process-wide PostgresSaver-backed instance).

Topology (5 nodes, simplified 2026-05-23):

    START
      ↓
    ask                                   ← interrupt() for participant reply
      ↓
    [judge_off | judge_standard | judge_deep]   ← route_after_ask
      ↓
    advance | ask                         ← route_after_judge
      ↓
    ask | END                             ← route_after_advance
                                            (END skips a finalize node;
                                            post_session pipeline produces
                                            the final report from
                                            InterviewSession.transcript)

All routing functions are **pure functions over state** (Rule 12). No
LLM call inside a routing function — that would let the AI decide flow,
which v3 explicitly forbids.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from langgraph.graph import END, START, StateGraph

from merism.conductor.configuration import Configuration
from merism.conductor.nodes import (
    advance_cursor,
    ask_and_wait,
    judge_deep,
    judge_off,
    judge_standard,
)
from merism.conductor.state import OverallState

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver


# ════════════════════════════════════════════════════════════════════
#  Routing functions — pure state -> Literal[node_name]. Rule 12.
# ════════════════════════════════════════════════════════════════════


def route_after_ask(state: OverallState) -> Literal["judge_off", "judge_standard", "judge_deep"]:
    """Dispatch the just-received answer to the configured judge mode.

    Mode is per-question (``Question.follow_up_mode``) — researchers can
    set background questions to ``off`` while pain-point deep-dives use
    ``deep``. Falls back to session-level ``state["follow_up_mode"]`` if
    the question doesn't carry a mode (defensive; shouldn't happen with
    Pydantic default ``"standard"``).
    """
    # Resolve current question and read its mode.
    from merism.conductor.schema import Outline

    outline_dict = state.get("outline")
    if outline_dict is not None:
        outline = Outline.model_validate(outline_dict)
        section_i = state.get("section_i", 0)
        question_i = state.get("question_i", 0)
        try:
            mode = outline.sections[section_i].questions[question_i].follow_up_mode
        except (IndexError, AttributeError):
            mode = state.get("follow_up_mode", "standard")
    else:
        mode = state.get("follow_up_mode", "standard")

    if mode == "off":
        return "judge_off"
    if mode == "deep":
        return "judge_deep"
    return "judge_standard"


def route_after_judge(state: OverallState) -> Literal["ask", "advance"]:
    """If the judge produced a probe, loop back to ``ask``; else advance."""
    return "ask" if state.get("pending_probe") else "advance"


def route_after_advance(state: OverallState) -> Literal["ask", "__end__"]:
    """End of outline → END; otherwise ask the next question."""
    return "__end__" if state.get("done") else "ask"


# ════════════════════════════════════════════════════════════════════
#  Graph builder
# ════════════════════════════════════════════════════════════════════


def build_graph(checkpointer: BaseCheckpointSaver | None = None) -> Any:
    """Compile the v3 state graph.

    Pass a ``checkpointer`` (e.g. ``PostgresSaver``) for production. Pass
    ``None`` only in tests that don't exercise resume/interrupt across
    process boundaries; LangGraph requires a checkpointer for ``interrupt()``
    to function in a multi-call session, so production callers MUST pass one.

    Return type is ``Any`` because the compiled graph's parametric return
    type (``CompiledStateGraph[OverallState, Configuration, ...]``) is
    invariant and pins us to specific generic params; ``Any`` lets callers
    treat the graph as an opaque executable runnable.
    """
    builder = StateGraph(OverallState, context_schema=Configuration)

    builder.add_node("ask", ask_and_wait)
    builder.add_node("judge_off", judge_off)
    builder.add_node("judge_standard", judge_standard)
    builder.add_node("judge_deep", judge_deep)
    builder.add_node("advance", advance_cursor)

    builder.add_edge(START, "ask")

    builder.add_conditional_edges(
        "ask",
        route_after_ask,
        {
            "judge_off": "judge_off",
            "judge_standard": "judge_standard",
            "judge_deep": "judge_deep",
        },
    )

    # All three judges feed into the same routing decision.
    for jnode in ("judge_off", "judge_standard", "judge_deep"):
        builder.add_conditional_edges(
            jnode,
            route_after_judge,
            {"ask": "ask", "advance": "advance"},
        )

    builder.add_conditional_edges(
        "advance",
        route_after_advance,
        {"ask": "ask", "__end__": END},
    )

    return builder.compile(checkpointer=checkpointer, name="conductor-v3")


__all__ = [
    "build_graph",
    "route_after_advance",
    "route_after_ask",
    "route_after_judge",
]
