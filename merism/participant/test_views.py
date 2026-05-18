"""End-to-end tests for the /i/<slug>/ participant flow."""

from __future__ import annotations

import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from merism.models import (
    InterviewGuide,
    InterviewSession,
    Organization,
    OrganizationMembership,
    Participation,
    Screener,
    Study,
    StudyLink,
    Team,
)

pytestmark = pytest.mark.django_db


def _bootstrap(
    *,
    with_screener: bool = False,
    target_completed: int = 10,
    link_active: bool = True,
    link_expired: bool = False,
) -> tuple[StudyLink, Screener | None]:
    User = get_user_model()
    User.objects.get_or_create(
        email="researcher@p.local", defaults={"username": "r", "is_active": True}
    )
    org, _ = Organization.objects.get_or_create(
        slug="p-org", defaults={"name": "POrg"}
    )
    team, _ = Team.objects.get_or_create(name="PTeam", organization=org)
    study = Study.objects.create(
        team=team,
        research_goal="participant flow test",
        status=Study.Status.LIVE,
        target_completed_count=target_completed,
    )
    # Every study needs a current guide for /start to succeed.
    InterviewGuide.objects.create(team=team, study=study, is_current=True)

    link = StudyLink.objects.create(
        study=study,
        team=team,
        is_active=link_active,
        expires_at=(
            timezone.now() - timezone.timedelta(days=1)
            if link_expired
            else None
        ) if link_expired else None,
    )

    screener = None
    if with_screener:
        screener = Screener.objects.create(
            team=team,
            study=study,
            questions=[
                {"id": "age", "text": "How old are you?", "kind": "number"},
                {"id": "uses", "text": "Do you use the product weekly?", "kind": "single"},
            ],
            pass_logic={
                "pass_threshold": 0.7,
                "question_weights": {"age": 0.3, "uses": 0.7},
                "correct_answers": {"uses": "yes"},
            },
        )

    return link, screener


# ── resolve_link ────────────────────────────────────────


def test_resolve_creates_participation_and_sets_cookie() -> None:
    link, _ = _bootstrap()
    c = Client()
    r = c.get(f"/i/{link.slug}/")
    assert r.status_code == 200, r.content
    body = r.json()
    assert body["ok"] is True
    assert body["next_step"] == "consent"
    assert body["participation"]["status"] == "invited"
    assert body["participation"]["is_preview"] is False
    assert "merism_browser_token" in r.cookies

    # Participation was actually persisted
    assert Participation.objects.filter(study=link.study).count() == 1


def test_resolve_recovers_existing_participation_via_cookie() -> None:
    link, _ = _bootstrap()
    c = Client()
    r1 = c.get(f"/i/{link.slug}/")
    token1 = r1.cookies["merism_browser_token"].value
    r2 = c.get(f"/i/{link.slug}/")
    assert r1.json()["participation"]["id"] == r2.json()["participation"]["id"]
    assert r2.cookies["merism_browser_token"].value == token1


def test_resolve_returns_410_when_link_inactive() -> None:
    link, _ = _bootstrap(link_active=False)
    r = Client().get(f"/i/{link.slug}/")
    assert r.status_code == 410
    assert r.json()["error_code"] == "link_closed"


def test_resolve_returns_404_for_unknown_slug() -> None:
    r = Client().get("/i/zzzzzzzzzz/")
    assert r.status_code == 404
    assert r.json()["error_code"] == "not_found"


def test_resolve_honours_quota() -> None:
    link, _ = _bootstrap(target_completed=1)
    # Fill the quota with a real completed participation
    Participation.objects.create(
        team=link.team,
        study=link.study,
        status=Participation.Status.COMPLETED,
        source=Participation.Source.DIRECT_LINK,
    )
    r = Client().get(f"/i/{link.slug}/")
    assert r.status_code == 409
    assert r.json()["error_code"] == "study_full"


def test_resolve_preview_mode_bypasses_quota() -> None:
    link, _ = _bootstrap(target_completed=1)
    Participation.objects.create(
        team=link.team,
        study=link.study,
        status=Participation.Status.COMPLETED,
        source=Participation.Source.DIRECT_LINK,
    )
    r = Client().get(f"/i/{link.slug}/?preview=1")
    assert r.status_code == 200
    assert r.json()["participation"]["is_preview"] is True


# ── consent ────────────────────────────────────────────


def test_consent_advances_status_and_next_step() -> None:
    link, _ = _bootstrap()
    c = Client()
    c.get(f"/i/{link.slug}/")
    r = c.post(f"/i/{link.slug}/consent/")
    assert r.status_code == 200, r.content
    body = r.json()
    assert body["participation"]["status"] == "consented"
    # No screener → next = session
    assert body["next_step"] == "session"


def test_consent_without_cookie_fails() -> None:
    link, _ = _bootstrap()
    r = Client().post(f"/i/{link.slug}/consent/")
    assert r.status_code == 403
    assert r.json()["error_code"] == "no_session"


# ── screener ───────────────────────────────────────────


def test_screener_get_returns_questions() -> None:
    link, screener = _bootstrap(with_screener=True)
    c = Client()
    c.get(f"/i/{link.slug}/")
    c.post(f"/i/{link.slug}/consent/")
    r = c.get(f"/i/{link.slug}/screener/")
    assert r.status_code == 200
    qs = r.json()["questions"]
    assert len(qs) == 2
    assert {q["id"] for q in qs} == {"age", "uses"}


def test_screener_post_passing_advances_to_session() -> None:
    link, _ = _bootstrap(with_screener=True)
    c = Client()
    c.get(f"/i/{link.slug}/")
    c.post(f"/i/{link.slug}/consent/")
    r = c.post(
        f"/i/{link.slug}/screener/",
        data=json.dumps({"answers": {"age": 30, "uses": "yes"}}),
        content_type="application/json",
    )
    assert r.status_code == 200, r.content
    body = r.json()
    assert body["passed"] is True
    assert body["participation"]["status"] == "screened"
    assert body["next_step"] == "session"


def test_screener_post_failing_drops_participation() -> None:
    link, _ = _bootstrap(with_screener=True)
    c = Client()
    c.get(f"/i/{link.slug}/")
    c.post(f"/i/{link.slug}/consent/")
    r = c.post(
        f"/i/{link.slug}/screener/",
        data=json.dumps({"answers": {"age": 30, "uses": "no"}}),
        content_type="application/json",
    )
    body = r.json()
    assert body["passed"] is False
    assert body["participation"]["status"] == "dropped"
    assert body["next_step"] == "dropped"


# ── start_session ──────────────────────────────────────


def test_start_session_creates_session_with_all_fks() -> None:
    link, _ = _bootstrap()
    c = Client()
    c.get(f"/i/{link.slug}/")
    c.post(f"/i/{link.slug}/consent/")
    r = c.post(f"/i/{link.slug}/start/")
    assert r.status_code == 200, r.content
    body = r.json()
    assert "session_id" in body
    session = InterviewSession.objects.get(id=body["session_id"])
    assert session.study_id == link.study.id
    assert session.team_id == link.team.id
    assert session.guide_id is not None
    assert session.participation.status == "interviewing"


def test_start_session_auto_creates_missing_current_guide() -> None:
    link, _ = _bootstrap()
    InterviewGuide.objects.filter(study=link.study).delete()
    c = Client()
    c.get(f"/i/{link.slug}/")
    c.post(f"/i/{link.slug}/consent/")
    r = c.post(f"/i/{link.slug}/start/")
    assert r.status_code == 200, r.content
    body = r.json()
    session = InterviewSession.objects.get(id=body["session_id"])
    assert session.guide.is_current is True
    assert session.guide.study_id == link.study.id
    assert InterviewGuide.objects.filter(study=link.study, is_current=True).count() == 1


def test_start_session_requires_consent() -> None:
    link, _ = _bootstrap()
    c = Client()
    c.get(f"/i/{link.slug}/")  # resolve only, no consent
    r = c.post(f"/i/{link.slug}/start/")
    assert r.status_code == 412
    assert r.json()["error_code"] == "consent_required"


def test_start_session_reuses_in_progress_session() -> None:
    link, _ = _bootstrap()
    c = Client()
    c.get(f"/i/{link.slug}/")
    c.post(f"/i/{link.slug}/consent/")
    first = c.post(f"/i/{link.slug}/start/").json()
    second = c.post(f"/i/{link.slug}/start/").json()
    assert first["session_id"] == second["session_id"]
    # Only one session in DB
    assert InterviewSession.objects.filter(study=link.study).count() == 1


def test_full_happy_path_with_screener() -> None:
    link, _ = _bootstrap(with_screener=True)
    c = Client()

    # 1) resolve
    r = c.get(f"/i/{link.slug}/")
    assert r.json()["next_step"] == "consent"

    # 2) consent
    r = c.post(f"/i/{link.slug}/consent/")
    assert r.json()["next_step"] == "screener"

    # 3) screener
    r = c.post(
        f"/i/{link.slug}/screener/",
        data=json.dumps({"answers": {"age": 30, "uses": "yes"}}),
        content_type="application/json",
    )
    assert r.json()["next_step"] == "session"

    # 4) start
    r = c.post(f"/i/{link.slug}/start/")
    body = r.json()
    assert body["next_step"] == "session"
    assert "session_id" in body
