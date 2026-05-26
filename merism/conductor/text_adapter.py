"""HTTP text-mode adapter — wraps the v3 graph for one-turn-per-request use.

Pattern provenance: design.md §10 + §11 + §13. The voice processor and
this text adapter both call into ``runner.start_interview`` /
``runner.answer_interview``; the difference is *who decides which to call*.

For voice, the pipecat processor explicitly calls ``start`` on
``StartFrame`` and ``answer`` on ``TranscriptionFrame``. For HTTP, the
client just sends a participant message; we infer "is this the first
turn?" by inspecting the LangGraph checkpoint via ``graph.get_state``.

The compiled graph itself is owned by :mod:`merism.conductor.factory` —
the factory is the single source of truth for the process-wide graph
instance. This module just consumes it. Voice mode consumes the same
factory; neither knows about the other.
"""

from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import sync_to_async

from merism.conductor.factory import get_graph
from merism.conductor.persistence import finalize_to_session
from merism.conductor.runner import (
    answer_interview,
    get_interrupt_payload,
    graph_config,
    start_interview,
)
from merism.conductor.schema import Outline

logger = logging.getLogger(__name__)


def _is_first_turn(graph: Any, thread_id: str) -> bool:
    """True if no checkpoint yet exists for this thread_id."""
    state = graph.get_state(graph_config(thread_id))
    if state is None:
        return True
    return not state.values


async def run_turn(
    *,
    session_id: str,
    user_message: str,
    outline: Outline,
    follow_up_mode: str,
) -> dict[str, Any]:
    """Run one turn of a v3 interview, returning the next question or done.

    Return shape::

        {
            "kind": "question" | "done" | "error",
            "question": str | None,
            "section_id": str | None,
            "question_id": str | None,
            "turn_kind": "main" | "followup" | None,
            "error": str | None,
        }

    No ``final_report`` field — v3 graph has no finalize node; reports
    are produced asynchronously by the post-session pipeline reading
    ``InterviewSession.transcript`` after :func:`finalize_to_session`
    flips ``status="completed"``.
    """
    graph = get_graph()

    try:
        if await sync_to_async(_is_first_turn)(graph, session_id):
            result = await sync_to_async(start_interview)(
                graph,
                outline=outline,
                thread_id=session_id,
                follow_up_mode=follow_up_mode,  # type: ignore[arg-type]
            )
        else:
            result = await sync_to_async(answer_interview)(graph, user_answer=user_message, thread_id=session_id)
    except Exception as exc:
        logger.exception("conductor.run_turn.failed session=%s", session_id)
        return {
            "kind": "error",
            "question": None,
            "section_id": None,
            "question_id": None,
            "turn_kind": None,
            "error": str(exc),
        }

    payload = get_interrupt_payload(result)
    if payload is not None:
        return {
            "kind": "question",
            "question": payload.get("question"),
            "section_id": payload.get("section_id"),
            "question_id": payload.get("question_id"),
            "turn_kind": payload.get("kind"),
            "error": None,
        }

    last_error = result.get("last_error")
    await finalize_to_session(graph, session_id)
    return {
        "kind": "done",
        "question": None,
        "section_id": None,
        "question_id": None,
        "turn_kind": None,
        "error": last_error,
    }


__all__ = ["run_turn"]
