"""Event log correctness: atomicity, ordering, replay."""

from __future__ import annotations

import threading
import uuid

import pytest
from django.db import connection, connections

from merism.conductor.event_log import (
    append_event,
    append_events,
    current_transcript,
    load_events,
    reconstruct_state,
)
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


def _boot() -> InterviewSession:
    org = Organization.objects.create(name="EL", slug=f"el-{uuid.uuid4().hex[:6]}")
    team = Team.objects.create(organization=org, name="ELT")
    study = Study.objects.create(team=team, research_goal="rg")
    guide = InterviewGuide.objects.create(
        team=team, study=study, is_current=True, sections=[]
    )
    participant = Participant.objects.create(team=team)
    participation = Participation.objects.create(
        study=study,
        team=team,
        participant=participant,
        # browser_token auto-generated
    )
    return InterviewSession.objects.create(
        study=study, team=team, participation=participation, guide=guide
    )


def test_append_event_allocates_monotonic_seq():
    s = _boot()
    e1 = append_event(s, "user_turn", {"text": "hi"})
    e2 = append_event(s, "model_reply", {"text": "hello"})
    e3 = append_event(s, "decision", {"decision": {"next_action": "move_on"}})
    assert [e1.seq, e2.seq, e3.seq] == [1, 2, 3]


def test_append_event_seq_never_collides_across_sessions():
    s1 = _boot()
    s2 = _boot()
    append_event(s1, "user_turn", {"text": "s1"})
    append_event(s2, "user_turn", {"text": "s2"})
    append_event(s1, "user_turn", {"text": "s1-2"})
    assert list(SessionEvent.objects.filter(session=s1).values_list("seq", flat=True).order_by("seq")) == [1, 2]
    assert list(SessionEvent.objects.filter(session=s2).values_list("seq", flat=True).order_by("seq")) == [1]


def test_append_events_batch_allocates_contiguous_seqs():
    s = _boot()
    rows = append_events(
        s,
        [
            ("user_turn", {"text": "q1"}),
            ("model_reply", {"text": "a1"}),
            ("decision", {"decision": {"next_action": "move_on"}}),
        ],
    )
    assert [r.seq for r in rows] == [1, 2, 3]


def test_current_transcript_projects_user_and_model_events():
    s = _boot()
    append_events(
        s,
        [
            ("user_turn", {"text": "hi"}),
            ("model_reply", {"text": "hello"}),
            ("decision", {"decision": {"next_action": "followup"}}),
            ("user_turn", {"text": "again"}),
            ("model_reply", {"text": "sure"}),
        ],
    )
    t = current_transcript(s)
    assert [(r["role"], r["text"]) for r in t] == [
        ("user", "hi"),
        ("assistant", "hello"),
        ("user", "again"),
        ("assistant", "sure"),
    ]


def test_reconstruct_state_folds_decisions():
    s = _boot()
    append_event(s, "state_transition", {"current_question_id": "q1", "phase": "active"})
    append_event(s, "user_turn", {"text": "hi"})
    append_event(s, "model_reply", {"text": "hello"})
    append_event(s, "decision", {"decision": {"next_action": "followup"}})
    append_event(s, "decision", {"decision": {"next_action": "move_on"}})
    state = reconstruct_state(s)
    assert state.last_action == "move_on"
    assert state.followups_used.get("q1", {}).get("asked", 0) == 1
    assert state.answered_question_ids == ["q1"]


def test_reconstruct_state_tracks_dynamic_probe_decision():
    s = _boot()
    append_event(s, "state_transition", {"current_question_id": "q1", "phase": "active"})
    append_event(
        s,
        "decision",
        {
            "decision": {
                "next_action": "followup",
                "probe_kind": "dynamic",
                "dynamic_trigger": "new_theme",
            }
        },
    )
    state = reconstruct_state(s)
    assert state.dynamic_probes_used.get("q1", {}).get("asked", 0) == 1
    assert state.followups_used.get("q1", {}).get("asked", 0) == 0


def test_reconstruct_state_close_decision_flips_phase():
    s = _boot()
    append_event(s, "decision", {"decision": {"next_action": "close"}})
    state = reconstruct_state(s)
    assert state.phase == "closing"


def test_reconstruct_state_lifecycle_ended_sets_phase_ended():
    s = _boot()
    append_event(s, "session_lifecycle", {"lifecycle": "ended"})
    assert reconstruct_state(s).phase == "ended"


def test_unique_together_enforced():
    s = _boot()
    append_event(s, "user_turn", {"text": "hi"})
    # direct insertion with duplicate seq should fail
    from django.db import IntegrityError
    with pytest.raises(IntegrityError):
        SessionEvent.objects.create(session=s, seq=1, kind="user_turn")


def test_load_events_returns_by_seq_order():
    s = _boot()
    append_event(s, "user_turn", {})
    append_event(s, "model_reply", {})
    append_event(s, "decision", {"decision": {}})
    ev = load_events(s)
    assert [e.seq for e in ev] == [1, 2, 3]
