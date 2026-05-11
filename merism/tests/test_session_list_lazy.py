"""Lazy-load contract: session list endpoint must NOT return transcript."""
from __future__ import annotations

import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from merism.models import (
    InterviewGuide,
    InterviewSession,
    Organization,
    OrganizationMembership,
    Participant,
    Participation,
    Study,
    Team,
)

pytestmark = pytest.mark.django_db


def _bootstrap() -> InterviewSession:
    User = get_user_model()
    u, _ = User.objects.get_or_create(
        email="lazy@test.local",
        defaults={"username": "lazy", "is_active": True},
    )
    org, _ = Organization.objects.get_or_create(
        slug="lazy-org", defaults={"name": "LazyOrg"}
    )
    OrganizationMembership.objects.get_or_create(
        organization=org, user=u, defaults={"role": "owner"}
    )
    team, _ = Team.objects.get_or_create(
        name="LazyTeam", organization=org
    )
    study = Study.objects.create(team=team, research_goal="lazy-test")
    guide = InterviewGuide.objects.create(team=team, study=study)
    participant = Participant.objects.create(team=team, name="p")
    participation = Participation.objects.create(
        team=team, study=study, participant=participant
    )
    transcript = [
        {"ts": i, "role": "participant", "text": f"turn {i} " + ("x" * 200)}
        for i in range(30)
    ]
    return InterviewSession.objects.create(
        team=team,
        study=study,
        participation=participation,
        guide=guide,
        transcript=transcript,
    )


def test_session_list_omits_transcript() -> None:
    session = _bootstrap()
    User = get_user_model()
    c = Client()
    c.force_login(User.objects.get(email="lazy@test.local"))

    r = c.get("/api/sessions/")
    assert r.status_code == 200, r.content[:500]
    body = r.json()
    results = body["results"] if isinstance(body, dict) else body
    row = next(x for x in results if x["id"] == str(session.id))

    assert "transcript" not in row, "transcript MUST be absent on list"
    assert "vision_frames" not in row
    assert row["turn_count"] == 30
    assert row["duration_seconds"] is None


def test_session_retrieve_includes_transcript() -> None:
    session = _bootstrap()
    User = get_user_model()
    c = Client()
    c.force_login(User.objects.get(email="lazy@test.local"))

    r = c.get(f"/api/sessions/{session.id}/")
    assert r.status_code == 200
    body = json.loads(r.content)
    assert "transcript" in body
    assert isinstance(body["transcript"], list)
    assert len(body["transcript"]) == 30
