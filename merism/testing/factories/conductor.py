"""Conductor-layer factories.

Conductor is the 3-layer pyramid (macro / meso / micro) that runs an interview
turn-by-turn. These factories build the state objects tests need to exercise
each layer in isolation.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any


def make_execution_state(
    *,
    phase: str = "active",
    turn_count: int = 0,
    current_question_id: str | None = None,
    answered_question_ids: list[str] | None = None,
    off_topic_streak: int = 0,
    time_elapsed_s: float = 0.0,
    next_action: str = "deepen",
    extra: dict[str, Any] | None = None,
) -> SimpleNamespace:
    """Build a conductor ``ExecutionState``.

    Phases: ``"warmup"`` → ``"active"`` → ``"closing"`` → ``"ended"``.
    ``next_action``: the Meso-layer decision one of
    ``"deepen"`` / ``"move_on"`` / ``"clarify"`` / ``"steer"`` / ``"end"``.
    """
    return SimpleNamespace(
        phase=phase,
        turn_count=turn_count,
        current_question_id=current_question_id,
        answered_question_ids=list(answered_question_ids or []),
        off_topic_streak=off_topic_streak,
        time_elapsed_s=time_elapsed_s,
        next_action=next_action,
        extra=extra or {},
        to_dict=_to_dict_factory(
            phase=phase,
            turn_count=turn_count,
            current_question_id=current_question_id,
            answered_question_ids=list(answered_question_ids or []),
            off_topic_streak=off_topic_streak,
            time_elapsed_s=time_elapsed_s,
            next_action=next_action,
            extra=extra or {},
        ),
    )


def make_policy_context(
    *,
    interview: SimpleNamespace | None = None,
    execution_state: SimpleNamespace | None = None,
    goals: list[SimpleNamespace] | None = None,
    participant_message: str = "",
    elapsed_minutes: float = 0.0,
    total_minutes: float = 30.0,
    extras: dict[str, Any] | None = None,
) -> SimpleNamespace:
    """Build the context passed to conductor policies (coverage_steer, engagement, off_topic).

    Keep this loose — every policy reads a slightly different subset.
    """
    return SimpleNamespace(
        interview=interview,
        state=execution_state,
        goals=goals or [],
        participant_message=participant_message,
        elapsed_minutes=elapsed_minutes,
        total_minutes=total_minutes,
        progress_ratio=(elapsed_minutes / total_minutes) if total_minutes else 0.0,
        extras=extras or {},
    )


def _to_dict_factory(**fields: Any):
    """Return a ``to_dict`` callable that preserves the construction kwargs."""

    def _to_dict() -> dict[str, Any]:
        return dict(fields)

    return _to_dict
