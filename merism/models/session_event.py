"""Session event log — event-sourced turn history for a moderated interview.

Each turn appends a small number of rows to this table (user_turn,
model_reply, decision, state_transition, optional interruption/error).
The canonical ``ExecutionState`` for a session is **reconstructed by
folding its events**; ``InterviewSession.moderator_state`` becomes a
cached materialized view that can be rebuilt at any time from the log.

Design notes
------------
- Single table, Postgres sequence-free; ``seq`` is a per-session monotone
  integer allocated inside a DB transaction (``select_for_update`` on the
  session row). This keeps the table writable from any worker without a
  dedicated coordinator.
- ``trace_id`` copies the owning Participation's id to allow
  cross-boundary correlation (invite → consent → session → insight).
- No foreign key back to ``Participation`` — keep this table
  session-scoped to avoid N+1 joins; trace_id is the correlation handle.
- Write paths should always go through ``merism.conductor.event_log``,
  never construct ``SessionEvent`` directly. The service module owns
  ordering and atomicity.
"""

from __future__ import annotations

import uuid

from django.db import models

from merism.models.interview import InterviewSession


class SessionEvent(models.Model):
    """An append-only log entry recording one turn-level fact."""

    class Kind(models.TextChoices):
        # v1 kinds (legacy ``merism.conductor`` runtime)
        USER_TURN = "user_turn", "user_turn"
        MODEL_REPLY = "model_reply", "model_reply"
        DECISION = "decision", "decision"
        STATE_TRANSITION = "state_transition", "state_transition"
        INTERRUPTION = "interruption", "interruption"
        ERROR = "error", "error"
        SESSION_LIFECYCLE = "session_lifecycle", "session_lifecycle"
        # v2 list-interpreter kinds (see ADR 0009 + requirements.md Req 10)
        QUESTION_ENTERED = "question_entered", "question_entered"
        SLOTS_EXTRACTED = "slots_extracted", "slots_extracted"
        PROBE_STARTED = "probe_started", "probe_started"
        SILENCE_OBSERVED = "silence_observed", "silence_observed"
        SESSION_COMPLETED = "session_completed", "session_completed"
        SESSION_INTERRUPTED = "session_interrupted", "session_interrupted"
        # ``error`` is shared with v1; v2 emits it via the engine's
        # try/except wrappers around AI extract / generate calls.

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        InterviewSession,
        related_name="events",
        on_delete=models.CASCADE,
    )
    trace_id = models.UUIDField(null=True, blank=True, db_index=True)
    seq = models.BigIntegerField()
    kind = models.CharField(max_length=32, choices=Kind.choices)
    payload = models.JSONField(default=dict, blank=True)
    # Which guide question was active when this event occurred.
    question_id = models.CharField(max_length=64, blank=True, default="")
    # Explicit turn counter (user speaks → turn increments).
    turn_number = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "merism_session_event"
        unique_together = [("session", "seq")]
        indexes = [
            models.Index(fields=["session", "seq"]),
            models.Index(fields=["session", "kind"]),
            models.Index(fields=["trace_id"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["session_id", "seq"]

    def __str__(self) -> str:  # pragma: no cover
        return f"<SessionEvent session={self.session_id} seq={self.seq} kind={self.kind}>"
