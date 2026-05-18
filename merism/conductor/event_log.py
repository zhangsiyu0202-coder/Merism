"""Event-log service for InterviewSession.

All writes to :class:`~merism.models.SessionEvent` should go through this
module. Direct ORM writes risk breaking ``seq`` monotonicity.

The write path is:

    with transaction.atomic():
        InterviewSession row is locked (select_for_update)
        seq := (max(seq) over session) + 1
        SessionEvent.objects.create(session=..., seq=seq, ...)

Under Postgres this is a single short-lived transaction; under sqlite
(test env) ``select_for_update`` is a no-op but the transaction scope
still serializes writes inside one connection.

Reading: :func:`reconstruct_state` replays the events in seq order and
folds them into an ``ExecutionState``. The folding logic owns the
semantics — events themselves are inert data.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any
from uuid import UUID

from django.db import transaction
from django.db.models import Max

from merism.conductor.state import ExecutionState
from merism.models import InterviewSession, SessionEvent

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Write path
# ─────────────────────────────────────────────────────────────


def append_event(
    session: InterviewSession,
    kind: str,
    payload: dict[str, Any] | None = None,
    *,
    trace_id: UUID | None = None,
    question_id: str = "",
    turn_number: int = 0,
) -> SessionEvent:
    """Append one event to the session log.

    Allocates ``seq = max(seq) + 1`` atomically inside a transaction.
    Safe under contention — concurrent writers serialize on the session
    row lock.
    """
    payload = payload or {}
    with transaction.atomic():
        (
            InterviewSession.objects.select_for_update()
            .filter(id=session.id)
            .values_list("id", flat=True)
            .first()
        )
        next_seq = (
            SessionEvent.objects.filter(session=session)
            .aggregate(m=Max("seq"))
            .get("m")
            or 0
        ) + 1
        return SessionEvent.objects.create(
            session=session,
            trace_id=trace_id,
            seq=next_seq,
            kind=kind,
            payload=payload,
            question_id=question_id,
            turn_number=turn_number,
        )


def append_events(
    session: InterviewSession,
    events: Iterable[tuple[str, dict[str, Any]]],
    *,
    trace_id: UUID | None = None,
    question_id: str = "",
    turn_number: int = 0,
) -> list[SessionEvent]:
    """Append a batch of events atomically, each getting a contiguous seq.

    Useful when one turn produces user_turn + model_reply + decision that
    should be visible as a unit.
    """
    out: list[SessionEvent] = []
    with transaction.atomic():
        (
            InterviewSession.objects.select_for_update()
            .filter(id=session.id)
            .values_list("id", flat=True)
            .first()
        )
        base = (
            SessionEvent.objects.filter(session=session)
            .aggregate(m=Max("seq"))
            .get("m")
            or 0
        )
        rows = []
        for idx, (kind, payload) in enumerate(events, start=1):
            rows.append(
                SessionEvent(
                    session=session,
                    trace_id=trace_id,
                    seq=base + idx,
                    kind=kind,
                    payload=payload or {},
                    question_id=question_id,
                    turn_number=turn_number,
                )
            )
        SessionEvent.objects.bulk_create(rows)
        out.extend(rows)
    return out


# ─────────────────────────────────────────────────────────────
# Read / projection path
# ─────────────────────────────────────────────────────────────


def load_events(session: InterviewSession) -> list[SessionEvent]:
    return list(SessionEvent.objects.filter(session=session).order_by("seq"))


def reconstruct_state(session: InterviewSession) -> ExecutionState:
    """Fold events into an ExecutionState.

    Contract:
    - ``user_turn`` / ``model_reply`` events contribute transcript shape
    - ``decision`` events flip ``last_action`` and bump preset/dynamic probe counters
    - ``state_transition`` events carry explicit ``current_question_id``
      / ``current_section_id`` / ``phase`` / ``turn_count`` /
      ``answered_question_ids`` / ``followups_used`` /
      ``dynamic_probes_used`` / ``expanded_sections`` /
      ``concept_by_question_id`` / ``concepts_shown`` /
      ``pending_stimulus_events`` keys that are applied verbatim
    """
    state = ExecutionState()
    state.session_id = session.id
    for ev in load_events(session):
        if ev.kind == SessionEvent.Kind.DECISION:
            decision = ev.payload.get("decision") or {}
            state.last_action = decision.get("next_action", state.last_action)
            if decision.get("next_action") == "followup":
                qid = state.current_question_id
                if qid:
                    if decision.get("probe_kind") == "dynamic":
                        state.mark_dynamic_probe_used(qid)
                    else:
                        state.mark_followup_used(qid)
            elif decision.get("next_action") == "move_on":
                if state.current_question_id:
                    state.mark_answered(state.current_question_id)
            elif decision.get("next_action") == "close":
                state.enter_closing()
        elif ev.kind == SessionEvent.Kind.STATE_TRANSITION:
            for key in (
                "current_question_id",
                "current_section_id",
                "phase",
                "turn_count",
                "answered_question_ids",
                "followups_used",
                "dynamic_probes_used",
                "expanded_sections",
                "concept_by_question_id",
                "concepts_shown",
                "pending_stimulus_events",
                "closing_rounds_remaining",
            ):
                if key in ev.payload:
                    setattr(state, key, ev.payload[key])
        elif ev.kind == SessionEvent.Kind.SESSION_LIFECYCLE:
            lifecycle = ev.payload.get("lifecycle")
            if lifecycle == "started":
                state.phase = ev.payload.get("initial_phase", "warmup")
            elif lifecycle == "ended":
                state.phase = "ended"
    return state


def current_transcript(session: InterviewSession) -> list[dict[str, Any]]:
    """Project user_turn + model_reply events into a transcript list.

    Shape matches ``InterviewSession.transcript`` for UI compatibility:
    ``[{"role": "user" | "assistant", "text": ..., "ts": iso8601}, ...]``
    """
    out: list[dict[str, Any]] = []
    for ev in load_events(session):
        if ev.kind == SessionEvent.Kind.USER_TURN:
            out.append(
                {
                    "role": "user",
                    "text": ev.payload.get("text", ""),
                    "ts": ev.created_at.isoformat() if ev.created_at else None,
                }
            )
        elif ev.kind == SessionEvent.Kind.MODEL_REPLY:
            out.append(
                {
                    "role": "assistant",
                    "text": ev.payload.get("text", ""),
                    "ts": ev.created_at.isoformat() if ev.created_at else None,
                }
            )
    return out


def generate_transcript_text(session: InterviewSession) -> str:
    """Generate a plain-text transcript from session events.

    Output format (one line per turn):
        [2026-05-14T12:30:01+08:00] Q:q1 T:3 user: 我觉得价格太高了
        [2026-05-14T12:30:03+08:00] Q:q1 T:3 assistant: 能具体说说哪方面让你觉得贵吗?

    Only includes user_turn and model_reply events.
    """
    lines: list[str] = []
    for ev in load_events(session):
        if ev.kind == SessionEvent.Kind.USER_TURN:
            role = "user"
            text = ev.payload.get("text", "")
        elif ev.kind == SessionEvent.Kind.MODEL_REPLY:
            role = "assistant"
            text = ev.payload.get("text", "")
        else:
            continue
        ts = ev.created_at.isoformat() if ev.created_at else ""
        q = f" Q:{ev.question_id}" if ev.question_id else ""
        t = f" T:{ev.turn_number}" if ev.turn_number else ""
        lines.append(f"[{ts}]{q}{t} {role}: {text}\n")
    return "".join(lines)
