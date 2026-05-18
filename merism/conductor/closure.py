"""Session closure — 6-signal OR logic for "when to set status=COMPLETED".

A moderated interview can terminate for many reasons. Relying on one
signal (e.g. "the LLM said close") is fragile — LLMs are trained to be
helpful and will often not close an interview on their own. Instead we
OR together six independent signals and accept the earliest match.

Signals
-------
A. **close_decision** — the moderator emitted ``next_action == "close"``.
B. **closing_grace** — once the moderator enters closing phase, keep the
   session alive for a few extra exchanges so the participant can ask
   follow-ups and hear a natural wrap-up before hard completion.
C. **all_p0_answered_after_min** — every P0 StudyGoal is_answered and
   elapsed >= ``study.min_duration_minutes`` (default 5). Prevents
   terminating a warmup-only session.
E. **leaving_intent** — the last user_turn matches a goodbye regex in
   the participant's locale.
F. **idle_timeout** — no user_turn event for > 120s.
G. **ws_disconnect** — the WebSocket has been disconnected for > 30s
   and the session has at least 4 turns (otherwise just a tyre-kicker).
H. **max_duration** — elapsed >= ``study.max_duration_minutes`` (default
   45).

Each signal returns a ``ClosureSignal`` if it fires, else ``None``.
``check_completion`` runs them in declaration order and returns the
first match (or None).

Side effects (applying the completion) are in ``complete_session`` so
callers can instrument the decision before acting.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

from django.db import transaction
from django.utils import timezone

from merism.models import InterviewSession, Participation, SessionEvent

logger = logging.getLogger(__name__)


Reason = Literal[
    "close_decision",
    "all_p0_answered",
    "leaving_intent",
    "idle_timeout",
    "ws_disconnect",
    "max_duration",
]


@dataclass(frozen=True)
class ClosureSignal:
    reason: Reason
    detail: str = ""


_LEAVING_PATTERNS = [
    re.compile(r"\b(thanks?|thank you|bye|goodbye|see you|i have to go|gotta go)\b", re.I),
    re.compile(r"(再见|拜拜|我得走了|就到这里|谢谢.{0,4}了)"),
]


def _leaving_intent(last_user_text: str) -> bool:
    return any(p.search(last_user_text) for p in _LEAVING_PATTERNS)


def check_completion(
    session: InterviewSession,
    *,
    ws_disconnected_seconds: int | None = None,
) -> ClosureSignal | None:
    """Run the six signals and return the first that fires.

    ``ws_disconnected_seconds`` is passed in by the voice consumer on
    disconnect; HTTP text-mode callers pass ``None``.
    """
    now = timezone.now()
    started_at = session.started_at or session.created_at
    elapsed = (now - started_at) if started_at else timedelta(0)
    moderator_state = session.moderator_state or {}
    closing_grace_remaining = int(moderator_state.get("closing_rounds_remaining") or 0)
    in_closing_grace = (
        moderator_state.get("phase") == "closing" and closing_grace_remaining > 0
    )

    # A. close decision
    last_decision = (session.decision_log or [])[-1] if session.decision_log else {}
    if last_decision.get("next_action") == "close" and not in_closing_grace:
        return ClosureSignal("close_decision")

    if moderator_state.get("phase") == "closing" and closing_grace_remaining <= 0:
        return ClosureSignal("close_decision", "closing grace exhausted")

    # Fetch the last user_turn event for signals C / D
    last_user_event = (
        SessionEvent.objects.filter(
            session=session, kind=SessionEvent.Kind.USER_TURN
        )
        .order_by("-seq")
        .first()
    )
    turn_count = SessionEvent.objects.filter(
        session=session, kind=SessionEvent.Kind.USER_TURN
    ).count()

    # B. P0 goals answered + past min duration
    study = session.study
    min_duration = timedelta(minutes=getattr(study, "min_duration_minutes", 5))
    if not in_closing_grace and elapsed >= min_duration and _all_p0_goals_answered(study):
        return ClosureSignal("all_p0_answered")

    # C. leaving intent
    if last_user_event and _leaving_intent(last_user_event.payload.get("text", "")):
        return ClosureSignal("leaving_intent")

    # D. idle timeout
    idle_cutoff = timedelta(seconds=120)
    if last_user_event and (now - last_user_event.created_at) >= idle_cutoff and turn_count >= 1:
        return ClosureSignal(
            "idle_timeout",
            f"silent for {int((now - last_user_event.created_at).total_seconds())}s",
        )

    # E. ws disconnect long enough + enough turns to be a real session
    if (
        ws_disconnected_seconds is not None
        and ws_disconnected_seconds >= 30
        and turn_count >= 4
    ):
        return ClosureSignal(
            "ws_disconnect", f"disconnected for {ws_disconnected_seconds}s"
        )

    # F. max duration
    max_duration = timedelta(minutes=getattr(study, "max_duration_minutes", 45))
    if elapsed >= max_duration:
        return ClosureSignal("max_duration", f"elapsed={int(elapsed.total_seconds())}s")

    return None


def _all_p0_goals_answered(study) -> bool:
    """``study.goals`` may not be populated for legacy studies; treat
    empty as "not yet closeable via this signal" (signal F will catch).
    """
    goals = getattr(study, "goals", None)
    if goals is None:
        return False
    try:
        p0 = list(goals.filter(priority="P0"))
    except Exception:
        return False
    if not p0:
        return False
    return all(getattr(g, "is_answered", False) for g in p0)


def complete_session(
    session: InterviewSession,
    signal: ClosureSignal,
) -> None:
    """Mark the session + participation COMPLETED inside one transaction.

    Emits a ``session_lifecycle`` event recording the triggering signal.
    Post-save signal on InterviewSession fires the Celery pipeline — we
    don't enqueue here to keep the trigger in one place.
    """
    from merism.conductor.event_log import append_event

    with transaction.atomic():
        # Re-read + lock so we don't race other signals.
        locked = (
            InterviewSession.objects.select_for_update()
            .select_related("participation")
            .get(id=session.id)
        )
        if locked.status == InterviewSession.Status.COMPLETED:
            logger.info("closure.already_completed", extra={"session_id": str(session.id)})
            return
        now = timezone.now()
        locked.status = InterviewSession.Status.COMPLETED
        locked.ended_at = now
        locked.save(update_fields=["status", "ended_at", "updated_at"])

        participation = locked.participation
        if participation and participation.status != Participation.Status.COMPLETED:
            participation.status = Participation.Status.COMPLETED
            participation.completed_at = now
            participation.save(update_fields=["status", "completed_at", "updated_at"])

        append_event(
            locked,
            SessionEvent.Kind.SESSION_LIFECYCLE,
            {"lifecycle": "ended", "reason": signal.reason, "detail": signal.detail},
            trace_id=locked.trace_id,
        )
    logger.info(
        "closure.completed",
        extra={
            "session_id": str(session.id),
            "reason": signal.reason,
            "detail": signal.detail,
        },
    )


def abandon_stuck_sessions(hours: int = 2) -> int:
    """Orphan cleanup. Sessions in_progress > ``hours`` → ABANDONED.

    Called by a Celery beat task; safe to invoke from admin actions or
    from tests. Returns the number of sessions modified.
    """
    from django.db.models import Q

    cutoff = timezone.now() - timedelta(hours=hours)
    stuck = InterviewSession.objects.filter(
        Q(status=InterviewSession.Status.PENDING)
        | Q(status=InterviewSession.Status.ACTIVE),
        updated_at__lt=cutoff,
    )
    count = 0
    for session in stuck.iterator():
        try:
            complete_session(
                session, ClosureSignal("max_duration", f"stuck > {hours}h")
            )
            count += 1
        except Exception:
            logger.exception(
                "closure.abandon_failed", extra={"session_id": str(session.id)}
            )
    return count
