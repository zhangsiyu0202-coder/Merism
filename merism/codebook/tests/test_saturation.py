"""Tests for :mod:`merism.codebook.saturation`."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from merism.codebook.models import CodebookVersion, CodeChange
from merism.codebook.saturation import is_codebook_saturated
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


@pytest.fixture(autouse=True)
def _disable_completed_session_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("merism.conductor.signals.process_completed_session.delay", lambda *args, **kwargs: None)


def _boot_study(suffix: str = "sat") -> tuple[Study, InterviewSession, InterviewSession, InterviewSession]:
    User = get_user_model()
    user = User.objects.create_superuser(
        username=f"sat-{suffix}@m.test", email=f"sat-{suffix}@m.test", password="x"
    )
    org = Organization.objects.create(name=f"Org {suffix}", slug=f"sat-{suffix}")
    team = Team.objects.create(name="Codebook", organization=org)
    study = Study.objects.create(team=team, created_by=user, research_goal="saturation")
    guide = InterviewGuide.objects.create(team=team, study=study, version="1.0.0", is_current=True, sections=[])
    participant = Participant.objects.create(team=team, external_id=f"p-{suffix}")

    sessions: list[InterviewSession] = []
    for idx in range(3):
        participation = Participation.objects.create(team=team, study=study, participant=participant)
        sessions.append(
            InterviewSession.objects.create(
                team=team,
                study=study,
                participation=participation,
                guide=guide,
                status=InterviewSession.Status.COMPLETED,
                ended_at=timezone.now() - timedelta(days=idx + 1),
            )
        )
    return study, sessions[0], sessions[1], sessions[2]


def _version_for(study: Study) -> CodebookVersion:
    return CodebookVersion.objects.create(
        team=study.team,
        study=study,
        version=1,
        codes=[],
    )


def test_is_codebook_saturated_requires_enough_completed_sessions() -> None:
    study, first, _second, _third = _boot_study("few")
    version = _version_for(study)
    change = CodeChange.objects.create(
        team=study.team,
        study=study,
        from_version=version,
        change_type=CodeChange.ChangeType.ADD,
        payload={},
        status=CodeChange.Status.APPLIED,
    )
    CodeChange.objects.filter(id=change.id).update(created_at=first.ended_at - timedelta(hours=1))

    assert is_codebook_saturated(study, lookback=4) is False


def test_is_codebook_saturated_uses_ended_at_threshold() -> None:
    study, _first, second, third = _boot_study("threshold")
    version = _version_for(study)
    change = CodeChange.objects.create(
        team=study.team,
        study=study,
        from_version=version,
        change_type=CodeChange.ChangeType.ADD,
        payload={},
        status=CodeChange.Status.APPLIED,
    )

    # Older than the oldest completed session in the lookback window.
    CodeChange.objects.filter(id=change.id).update(created_at=third.ended_at - timedelta(hours=1))
    assert is_codebook_saturated(study) is True

    # Now move it inside the window; saturation should flip back to False.
    CodeChange.objects.filter(id=change.id).update(created_at=second.ended_at + timedelta(hours=1))
    assert is_codebook_saturated(study) is False
