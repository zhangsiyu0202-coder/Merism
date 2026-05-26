"""Bridge: copy v3 graph terminal state into ``InterviewSession`` row.

Pattern provenance: design.md §11. v3 does not write per-turn
``SessionEvent`` rows (Rule 9 relaxed); the LangGraph checkpointer is the
runtime authority for resume/replay. The final transcript lands on
``InterviewSession.transcript`` once at session end so existing
post-session pipeline (``merism.conductor.post_session`` + insight
generators) can produce the report.

v3 has no ``finalize_interview`` node — final-report generation is fully
delegated to the existing post-session infrastructure rather than
duplicated inside the graph.

This is the only module in conductor that imports Django models. All
other modules stay ORM-free so they can be unit-tested without
django_db.
"""

from __future__ import annotations

from typing import Any

from asgiref.sync import sync_to_async
from django.db import transaction

from merism.conductor.runner import graph_config


async def finalize_to_session(graph: Any, session_id: str) -> bool:
    """Copy graph state's transcript into the session row.

    Returns ``True`` if the row was updated; ``False`` if the graph hasn't
    finished (``done=False``) or the session is already marked completed.

    Idempotent: re-calling on a completed session is a no-op (the
    ``.exclude(status="completed")`` filter ensures we don't double-write
    or overwrite a manually-marked session).

    The transcript is the only payload written here. Final reports are
    produced asynchronously by the post-session pipeline reading
    ``InterviewSession.transcript``.
    """
    state = await graph.aget_state(graph_config(session_id))
    if state is None or not state.values.get("done"):
        return False

    transcript = list(state.values.get("transcript", []))
    last_error = state.values.get("last_error")

    rows_updated = await sync_to_async(_apply_finalization)(
        session_id=session_id,
        transcript=transcript,
        last_error=last_error,
    )
    return bool(rows_updated)


def _apply_finalization(
    *,
    session_id: str,
    transcript: list[dict[str, Any]],
    last_error: str | None,
) -> int:
    """Write the v3 final state to the InterviewSession row.

    Atomic single-row update. Excludes already-completed sessions for
    idempotency. Returns the number of rows actually updated (0 = was
    already completed; 1 = freshly finalized).

    The v3 graph stores turns as ``{section_id, question_id, kind,
    question, answer}``. We expand each v3 turn into TWO v1-compatible
    transcript entries (``{role: agent, text}`` + ``{role: participant,
    text}``) so the existing post-session pipeline (cleaning + insight
    generation + reports) reads it like any v1 session. The original
    v3-shape turns are also preserved on ``moderator_state.v3_transcript``
    for any v3-aware analytics that wants the structured form.
    """
    # Local import — module-level import would create a Django app-loading
    # ordering hazard since conductor is imported before models are ready
    # in some test paths.
    from merism.models import InterviewSession

    v1_compat: list[dict[str, Any]] = []
    for turn in transcript:
        v1_compat.append(
            {
                "role": "agent",
                "text": turn["question"],
                "question_id": turn["question_id"],
                "kind": turn["kind"],
            }
        )
        v1_compat.append(
            {
                "role": "participant",
                "text": turn["answer"],
                "question_id": turn["question_id"],
            }
        )

    moderator_state: dict[str, Any] = {
        "engine": "v3",
        "v3_transcript": transcript,  # original shape preserved for v3-aware tools
    }
    if last_error:
        moderator_state["last_error"] = last_error

    with transaction.atomic():
        session = (
            InterviewSession.objects.select_for_update()
            .filter(id=session_id)
            .exclude(status="completed")
            .first()
        )
        if session is None:
            return 0

        session.transcript = v1_compat
        session.moderator_state = moderator_state
        session.status = InterviewSession.Status.COMPLETED
        session.save(update_fields=["moderator_state", "status", "transcript", "updated_at"])
        return 1


__all__ = ["finalize_to_session"]
