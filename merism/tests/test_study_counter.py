"""Aggregate-based Study completion counter + auto-close."""

from __future__ import annotations

import uuid

import pytest

from merism.models import (
    InterviewGuide,
    Organization,
    Participant,
    Participation,
    Study,
    StudyLink,
    Team,
)

pytestmark = pytest.mark.django_db


def _boot(target=2):
    org = Organization.objects.create(name="Ct", slug=f"ct-{uuid.uuid4().hex[:6]}")
    team = Team.objects.create(organization=org, name="CtT")
    study = Study.objects.create(
        team=team,
        research_goal="counter test",
        status=Study.Status.LIVE,
        target_completed_count=target,
    )
    InterviewGuide.objects.create(team=team, study=study, is_current=True, sections=[])
    link = StudyLink.objects.create(study=study, team=team)
    return team, study, link


def _add_participation(team, study, *, status, is_preview=False):
    participant = Participant.objects.create(team=team)
    return Participation.objects.create(
        study=study,
        team=team,
        participant=participant,
        status=status,
        is_preview=is_preview,
    )


def test_actual_completed_count_is_zero_initially():
    team, study, _ = _boot()
    assert study.actual_completed_count == 0


def test_actual_completed_count_counts_only_completed_non_preview():
    team, study, _ = _boot()
    _add_participation(team, study, status=Participation.Status.INTERVIEWING)
    _add_participation(team, study, status=Participation.Status.COMPLETED)
    _add_participation(team, study, status=Participation.Status.COMPLETED, is_preview=True)
    _add_participation(team, study, status=Participation.Status.DROPPED)
    assert study.actual_completed_count == 1


def test_annotate_completed_count_matches_property():
    team, study, _ = _boot()
    _add_participation(team, study, status=Participation.Status.COMPLETED)
    _add_participation(team, study, status=Participation.Status.COMPLETED)
    row = Study.annotate_completed_count().filter(id=study.id).first()
    assert row.actual_completed_count_annot == 2


def test_auto_close_when_target_reached():
    team, study, link = _boot(target=2)
    # Two completions fire two post_save signals.
    p1 = _add_participation(team, study, status=Participation.Status.INTERVIEWING)
    p2 = _add_participation(team, study, status=Participation.Status.INTERVIEWING)
    p1.status = Participation.Status.COMPLETED
    p1.save()
    study.refresh_from_db()
    # still open, only 1 completed.
    assert study.status == Study.Status.LIVE
    p2.status = Participation.Status.COMPLETED
    p2.save()
    study.refresh_from_db()
    link.refresh_from_db()
    # Auto-close flips the Study.status (metadata for inbox / analytics)
    # but does NOT deactivate the link. Link access is researcher-
    # controlled per the 2026-05-23 simplification (link.is_active toggle
    # in the Recruit tab).
    assert study.status == Study.Status.CLOSED
    assert link.is_active is True


def test_auto_close_ignores_preview_completions():
    team, study, link = _boot(target=1)
    p = _add_participation(team, study, status=Participation.Status.INTERVIEWING, is_preview=True)
    p.status = Participation.Status.COMPLETED
    p.save()
    study.refresh_from_db()
    assert study.status == Study.Status.LIVE
