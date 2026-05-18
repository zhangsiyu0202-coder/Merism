"""Moderator event-contract tests.

These tests intentionally stop at the event boundary. The async
``stream_turn`` path is covered elsewhere; here we verify the
deterministic contract that must hold after a moderator decision:

- user/model/decision/state_transition events are appended
- validator overrides are persisted in the decision event
- dynamic probe decisions reconstruct into dynamic session state

This avoids sqlite + async ORM thread-locking during unit tests while
still asserting the authoritative event log shape.
"""

from __future__ import annotations

import copy
import uuid

import pytest

from merism.conductor.decision_validator import validate_decision
from merism.conductor.event_log import append_events, reconstruct_state
from merism.conductor.moderator import _apply_decision_to_state
from merism.conductor.prompts import ModeratorDecision
from merism.conductor.state import ExecutionState
from merism.models import (
    InterviewGuide,
    InterviewSession,
    Organization,
    Participant,
    Participation,
    SessionEvent,
    Study,
    Team,
)


pytestmark = pytest.mark.django_db


def _boot_session() -> InterviewSession:
    org = Organization.objects.create(name="Mod", slug=f"mod-{uuid.uuid4().hex[:6]}")
    team = Team.objects.create(organization=org, name="MT")
    study = Study.objects.create(team=team, research_goal="test moderator events")
    guide = InterviewGuide.objects.create(
        team=team,
        study=study,
        is_current=True,
        sections=[
            {
                "id": "s1",
                "title": "Warm-up",
                "scope": "global",
                "questions": [
                    {
                        "id": "q1",
                        "text": "Tell me.",
                        "probe_policy": "light",
                        "max_probes": 2,
                        "probe_blocks": [{"id": "pb_0", "type": "custom", "prompt": "specific example", "trigger": "always", "max_rounds": 2, "priority": 1}, {"id": "pb_1", "type": "custom", "prompt": "workaround", "trigger": "always", "max_rounds": 2, "priority": 2}],
                        "dynamic_probe": {
                            "enabled": True,
                            "max_extra_rounds": 1,
                            "triggers": ["new_theme", "strong_emotion"],
                        },
                    },
                    {"id": "q2", "text": "And then?", "probe_policy": "light", "max_probes": 2},
                ],
            }
        ],
    )
    participant = Participant.objects.create(team=team)
    participation = Participation.objects.create(
        study=study,
        team=team,
        participant=participant,
    )
    return InterviewSession.objects.create(
        team=team,
        study=study,
        participation=participation,
        guide=guide,
        trace_id=participation.trace_id,
        moderator_state={"current_section_id": "s1", "current_question_id": "q1", "phase": "active"},
    )


def _append_turn_events(
    session: InterviewSession,
    *,
    participant_message: str,
    assistant_text: str,
    decision: ModeratorDecision,
    state: ExecutionState,
    qid_at_turn: str,
    validator_overridden: bool = False,
    validator_reason: str | None = None,
) -> None:
    append_events(
        session,
        [
            ("user_turn", {"text": participant_message, "question_id": qid_at_turn}),
            ("model_reply", {"text": assistant_text, "question_id": qid_at_turn}),
            (
                "decision",
                {
                    "decision": {
                        "next_action": decision.next_action,
                        "next_question_id": decision.next_question_id,
                        "probe_type": decision.probe_type,
                        "probe_kind": decision.probe_kind,
                        "dynamic_trigger": decision.dynamic_trigger,
                        "matches_rule": decision.matches_rule,
                        "think_notes": decision.think_notes,
                        "target_goal_id": decision.target_goal_id,
                        "off_topic": decision.off_topic,
                        "steering_strategy": decision.steering_strategy,
                    },
                    "validator_overridden": validator_overridden,
                    "validator_reason": validator_reason,
                },
            ),
            (
                "state_transition",
                {
                    "current_question_id": state.current_question_id,
                    "current_section_id": state.current_section_id,
                    "phase": state.phase,
                    "closing_rounds_remaining": state.closing_rounds_remaining,
                    "turn_count": state.turn_count,
                    "answered_question_ids": copy.deepcopy(state.answered_question_ids),
                    "followups_used": copy.deepcopy(state.followups_used),
                    "dynamic_probes_used": copy.deepcopy(state.dynamic_probes_used),
                    "expanded_sections": copy.deepcopy(state.expanded_sections),
                    "concept_by_question_id": copy.deepcopy(state.concept_by_question_id),
                    "concepts_shown": copy.deepcopy(state.concepts_shown),
                    "pending_stimulus_events": copy.deepcopy(state.pending_stimulus_events),
                },
            ),
        ],
        trace_id=session.trace_id,
    )


def test_stream_turn_logs_events_per_turn() -> None:
    session = _boot_session()
    state = ExecutionState.model_validate(session.moderator_state or {})
    state.followups_used["q1"] = {"asked": 0, "budget": 2}

    decision = ModeratorDecision(next_action="move_on", next_question_id="q2")
    qid_at_turn = state.current_question_id
    _apply_decision_to_state(state, decision, session.guide.sections or [])
    _append_turn_events(
        session,
        participant_message="I use it daily.",
        assistant_text="Thanks for sharing.",
        decision=decision,
        state=state,
        qid_at_turn=qid_at_turn,
    )

    events = list(SessionEvent.objects.filter(session=session).order_by("seq"))
    kinds = [e.kind for e in events]
    assert kinds == ["user_turn", "model_reply", "decision", "state_transition"]
    assert events[0].payload["text"] == "I use it daily."
    assert events[1].payload["text"] == "Thanks for sharing."
    assert events[2].payload["decision"]["next_action"] == "move_on"
    assert all(e.trace_id == session.trace_id for e in events)


def test_stream_turn_max_probes_forces_move_on() -> None:
    session = _boot_session()
    question = session.guide.sections[0]["questions"][0]
    state = ExecutionState.model_validate(session.moderator_state or {})
    state.followups_used["q1"] = {"asked": 2, "budget": 2}

    proposed = ModeratorDecision(
        next_action="followup",
        probe_type="expansion",
        probe_triggered_by="vague",
    )
    validation = validate_decision(
        proposed,
        question=question,
        probes_done=2,
        sections=session.guide.sections or [],
        dynamic_probes_done=0,
    )
    assert validation.overridden is True
    assert validation.decision.next_action == "move_on"

    qid_at_turn = state.current_question_id
    _apply_decision_to_state(state, validation.decision, session.guide.sections or [])
    _append_turn_events(
        session,
        participant_message="and then",
        assistant_text="Go on.",
        decision=validation.decision,
        state=state,
        qid_at_turn=qid_at_turn,
        validator_overridden=validation.overridden,
        validator_reason=validation.reason,
    )

    decision_event = SessionEvent.objects.filter(session=session, kind="decision").latest("seq")
    assert decision_event.payload["validator_overridden"] is True
    assert decision_event.payload["decision"]["next_action"] == "move_on"


def test_stream_turn_dynamic_probe_round_trips() -> None:
    session = _boot_session()
    state = ExecutionState.model_validate(session.moderator_state or {})
    state.followups_used["q1"] = {"asked": 0, "budget": 2}
    state.dynamic_probes_used["q1"] = {"asked": 0, "budget": 1}

    decision = ModeratorDecision(
        next_action="followup",
        probe_type="reasoning",
        probe_kind="dynamic",
        dynamic_trigger="new_theme",
        probe_triggered_by="participant introduced a new workflow",
    )
    qid_at_turn = state.current_question_id
    _apply_decision_to_state(state, decision, session.guide.sections or [])
    _append_turn_events(
        session,
        participant_message="I also built a spreadsheet workaround for it.",
        assistant_text="Can you walk me through that new workflow a bit more?",
        decision=decision,
        state=state,
        qid_at_turn=qid_at_turn,
    )

    decision_event = SessionEvent.objects.filter(session=session, kind="decision").latest("seq")
    assert decision_event.payload["decision"]["probe_kind"] == "dynamic"
    assert decision_event.payload["decision"]["dynamic_trigger"] == "new_theme"

    rebuilt_state = reconstruct_state(session)
    assert rebuilt_state.dynamic_probes_used.get("q1", {}).get("asked", 0) == 1
    assert rebuilt_state.followups_used.get("q1", {}).get("asked", 0) == 0


def test_close_decision_enters_closing_grace() -> None:
    session = _boot_session()
    state = ExecutionState.model_validate(session.moderator_state or {})

    decision = ModeratorDecision(next_action="close")
    qid_at_turn = state.current_question_id
    _apply_decision_to_state(state, decision, session.guide.sections or [])

    assert state.phase == "closing"
    assert state.closing_rounds_remaining == 3

    _append_turn_events(
        session,
        participant_message="thanks",
        assistant_text="谢谢你。",
        decision=decision,
        state=state,
        qid_at_turn=qid_at_turn,
    )

    rebuilt_state = reconstruct_state(session)
    assert rebuilt_state.phase == "closing"
    assert rebuilt_state.closing_rounds_remaining == 3


def test_closing_grace_counts_down_on_followup_turns() -> None:
    session = _boot_session()
    state = ExecutionState.model_validate(session.moderator_state or {})
    state.phase = "closing"
    state.closing_rounds_remaining = 2

    decision = ModeratorDecision(next_action="clarify")
    qid_at_turn = state.current_question_id
    _apply_decision_to_state(state, decision, session.guide.sections or [])

    assert state.phase == "closing"
    assert state.closing_rounds_remaining == 1

    _append_turn_events(
        session,
        participant_message="one more thing",
        assistant_text="可以，具体说说。",
        decision=decision,
        state=state,
        qid_at_turn=qid_at_turn,
    )

    rebuilt_state = reconstruct_state(session)
    assert rebuilt_state.phase == "closing"
    assert rebuilt_state.closing_rounds_remaining == 1
