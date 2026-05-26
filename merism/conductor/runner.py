"""High-level entry points to start, answer, and resume a v3 interview.

Pattern provenance: design.md §0 / pattern 10. Wraps the compiled graph
with thread_id management and the ``__interrupt__`` payload extractor.
Callers (HTTP view, voice processor, CLI) talk only to these functions —
they never construct ``Command(resume=...)`` directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, cast

from langgraph.types import Command

from merism.conductor.schema import Outline

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig
    from langgraph.graph.state import CompiledStateGraph


def graph_config(thread_id: str, *, configurable: dict[str, Any] | None = None) -> RunnableConfig:
    """Build the per-call config carrying ``thread_id`` (LangGraph session
    key) plus optional per-call overrides (model name, temperature, etc.)
    that ``Configuration.from_runnable_config`` consumes inside nodes.
    """
    cfg: dict[str, Any] = {"thread_id": thread_id}
    if configurable:
        cfg.update(configurable)
    return cast("RunnableConfig", {"configurable": cfg})


def start_interview(
    graph: CompiledStateGraph,
    *,
    outline: Outline,
    thread_id: str,
    follow_up_mode: Literal["off", "standard", "deep"] = "standard",
    configurable: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Begin a new interview session.

    Initial state seeds cursor at (0, 0), empty transcript, configured
    follow_up_mode. The graph runs until the first ``interrupt()`` (i.e.
    the first ``ask_and_wait``), then returns the in-flight state with
    the interrupt payload at ``result["__interrupt__"]``. Caller extracts
    it via :func:`get_interrupt_payload`.
    """
    initial: dict[str, Any] = {
        "outline": outline.model_dump(),
        "follow_up_mode": follow_up_mode,
        "section_i": 0,
        "question_i": 0,
        "probe_count": 0,
        "pending_probe": None,
        "transcript": [],
        "done": False,
    }
    return graph.invoke(initial, config=graph_config(thread_id, configurable=configurable))


def answer_interview(
    graph: CompiledStateGraph,
    *,
    user_answer: str,
    thread_id: str,
    configurable: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resume the interview with the participant's text answer.

    Calls into the checkpointed thread; the graph runs from the last
    ``interrupt()`` to the next one (or to ``END`` if the outline is done).
    """
    return graph.invoke(
        Command(resume=user_answer),
        config=graph_config(thread_id, configurable=configurable),
    )


def get_interrupt_payload(result: dict[str, Any]) -> dict[str, Any] | None:
    """Pull the question payload out of the LangGraph ``__interrupt__`` slot.

    Returns ``None`` when the graph reached ``END`` (no pending interrupt).
    LangGraph's interrupt object exposes its payload via ``.value``;
    different versions wrap it slightly differently, so we tolerate dict
    and object shapes.
    """
    interrupts = result.get("__interrupt__")
    if not interrupts:
        return None
    first = interrupts[0]
    if hasattr(first, "value"):
        return first.value
    if isinstance(first, dict) and "value" in first:
        return first["value"]
    if isinstance(first, dict):
        return first
    return None


__all__ = [
    "answer_interview",
    "get_interrupt_payload",
    "graph_config",
    "start_interview",
]
