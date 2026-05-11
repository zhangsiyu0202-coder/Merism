"""trace_id flows invite → session → insight."""

from __future__ import annotations

import uuid

import pytest

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
    org = Organization.objects.create(name="T", slug=f"t-{uuid.uuid4().hex[:6]}")
    team = Team.objects.create(organization=org, name="TT")
    study = Study.objects.create(team=team, research_goal="rg")
    guide = InterviewGuide.objects.create(team=team, study=study, is_current=True, sections=[])
    participant = Participant.objects.create(team=team)
    participation = Participation.objects.create(
        study=study, team=team, participant=participant
    )
    return org, team, study, guide, participation


def test_participation_has_default_trace_id():
    _, _, _, _, p = _boot()
    assert isinstance(p.trace_id, uuid.UUID)


def test_interview_session_copies_trace_id_when_set():
    _, team, study, guide, p = _boot()
    s = InterviewSession.objects.create(
        team=team, study=study, participation=p, guide=guide, trace_id=p.trace_id
    )
    assert s.trace_id == p.trace_id


def test_bind_trace_context_manager_sets_and_clears_key():
    import structlog.contextvars as cv
    from merism.observability import bind_trace

    tid = uuid.uuid4()
    # Before
    assert "trace_id" not in cv.get_contextvars()
    with bind_trace(trace_id=tid):
        assert cv.get_contextvars().get("trace_id") == str(tid)
    # After
    assert "trace_id" not in cv.get_contextvars()


def test_bind_trace_none_does_not_bind_key():
    import structlog.contextvars as cv
    from merism.observability import bind_trace

    with bind_trace(trace_id=None):
        assert "trace_id" not in cv.get_contextvars()
