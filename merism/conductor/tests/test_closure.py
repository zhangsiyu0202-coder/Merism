"""6-signal closure + orphan cleanup."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from merism.conductor.closure import (
    ClosureSignal,
    abandon_stuck_sessions,
    check_completion,
    complete_session,
)
from merism.conductor.event_log import append_event
from merism.models import (
    InterviewGuide,
    InterviewSession,
    Organization,
    Participant,
    Participation,
    Study,
    Team,
)


pytestmark = pytest.mark.django_db


def _boot():
    org = Organization.objects.create(name="Cl", slug=f"cl-{uuid.uuid4().hex[:6]}")
    team = Team.objects.create(organization=org, name="CT")
    study = Study.objects.create(team=team, research_goal="closure")
    guide = InterviewGuide.objects.create(team=team, study=study, is_current=True, sections=[])
    participant = Participant.objects.create(team=team)
    p = Participation.objects.create(study=study, team=team, participant=participant)
    s = InterviewSession.objects.create(
        team=team, study=study, participation=p, guide=guide, trace_id=p.trace_id,
        status=InterviewSession.Status.ACTIVE,
        started_at=timezone.now() - timedelta(minutes=1),
    )
    return p, s


def test_close_decision_signal_fires():
    _, s = _boot()
    s.decision_log = [{"next_action": "close"}]
    s.save(update_fields=["decision_log"])
    signal = check_completion(s)
    assert signal and signal.reason == "close_decision"


def test_leaving_intent_regex_fires():
    _, s = _boot()
    append_event(s, "user_turn", {"text": "Thanks, I think we're done here."})
    signal = check_completion(s)
    assert signal and signal.reason == "leaving_intent"


def test_max_duration_signal_fires():
    _, s = _boot()
    s.started_at = timezone.now() - timedelta(minutes=60)
    s.save(update_fields=["started_at"])
    signal = check_completion(s)
    assert signal and signal.reason == "max_duration"


def test_no_signal_when_fresh():
    _, s = _boot()
    signal = check_completion(s)
    assert signal is None


def test_complete_session_marks_both_session_and_participation():
    p, s = _boot()
    complete_session(s, ClosureSignal("close_decision"))
    s.refresh_from_db()
    p.refresh_from_db()
    assert s.status == InterviewSession.Status.COMPLETED
    assert s.ended_at is not None
    assert p.status == Participation.Status.COMPLETED
    assert p.completed_at is not None


def test_complete_session_is_idempotent():
    _, s = _boot()
    complete_session(s, ClosureSignal("close_decision"))
    # Second call should no-op (no raise).
    complete_session(s, ClosureSignal("max_duration"))


def test_abandon_stuck_sessions_moves_old_pending_to_completed():
    p, s = _boot()
    # Force updated_at to 3 hours ago (sqlite accepts the update).
    InterviewSession.objects.filter(id=s.id).update(
        updated_at=timezone.now() - timedelta(hours=3),
        status=InterviewSession.Status.PENDING,
    )
    count = abandon_stuck_sessions(hours=2)
    s.refresh_from_db()
    assert count == 1
    assert s.status == InterviewSession.Status.COMPLETED
