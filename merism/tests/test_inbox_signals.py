"""Inbox notifications + dedup."""

from __future__ import annotations

import uuid

import pytest

from merism.models import (
    InboxItem,
    InterviewGuide,
    InterviewSession,
    Organization,
    Participant,
    Participation,
    SessionInsight,
    Study,
    Team,
)


pytestmark = pytest.mark.django_db


def _boot():
    org = Organization.objects.create(name="Ib", slug=f"ib-{uuid.uuid4().hex[:6]}")
    team = Team.objects.create(organization=org, name="IbT")
    study = Study.objects.create(
        team=team, research_goal="inbox", status=Study.Status.RECRUITING,
        target_completed_count=1,
    )
    guide = InterviewGuide.objects.create(team=team, study=study, is_current=True, sections=[])
    participant = Participant.objects.create(team=team)
    p = Participation.objects.create(study=study, team=team, participant=participant)
    s = InterviewSession.objects.create(
        team=team, study=study, participation=p, guide=guide, trace_id=p.trace_id,
        status=InterviewSession.Status.ACTIVE,
    )
    return team, study, p, s


def test_session_completed_writes_inbox_item():
    team, study, p, s = _boot()
    s.status = InterviewSession.Status.COMPLETED
    s.save(update_fields=["status"])
    item = InboxItem.objects.filter(team=team, kind=InboxItem.Kind.SESSION_COMPLETED).first()
    assert item is not None
    assert item.ref_id == str(s.id)


def test_session_completed_is_idempotent():
    team, study, p, s = _boot()
    s.status = InterviewSession.Status.COMPLETED
    s.save(update_fields=["status"])
    s.save(update_fields=["status"])  # fires signal again
    count = InboxItem.objects.filter(team=team, kind=InboxItem.Kind.SESSION_COMPLETED).count()
    assert count == 1


def test_insight_created_writes_inbox_item():
    team, study, p, s = _boot()
    insight = SessionInsight.objects.create(
        team=team, session=s, summary="nice", tags=[],
    )
    item = InboxItem.objects.filter(team=team, kind=InboxItem.Kind.INSIGHT_READY).first()
    assert item is not None
    assert item.ref_id == str(insight.id)


def test_study_closed_writes_inbox_item():
    team, study, p, s = _boot()
    # Directly close the study
    study.status = Study.Status.CLOSED
    study.save(update_fields=["status"])
    item = InboxItem.objects.filter(team=team, kind=InboxItem.Kind.STUDY_COMPLETED).first()
    assert item is not None


def test_study_closed_via_autoclose_writes_item():
    team, study, p, s = _boot()
    # Hitting target through participation signal should auto-close study → write item
    p.status = Participation.Status.COMPLETED
    p.save(update_fields=["status"])
    study.refresh_from_db()
    assert study.status == Study.Status.CLOSED
    assert InboxItem.objects.filter(team=team, kind=InboxItem.Kind.STUDY_COMPLETED).exists()
