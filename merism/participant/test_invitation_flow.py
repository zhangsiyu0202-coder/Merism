"""Invitation flow — per-recipient token guards /i/<slug>/."""

from __future__ import annotations

import json
import uuid

import pytest
from django.test.client import Client

from merism.models import (
    InterviewGuide,
    Invitation,
    Organization,
    Participation,
    Study,
    StudyLink,
    Team,
)


pytestmark = pytest.mark.django_db


def _boot(require_invitation: bool = False):
    org = Organization.objects.create(name="Inv", slug=f"inv-{uuid.uuid4().hex[:6]}")
    team = Team.objects.create(organization=org, name="InvT")
    study = Study.objects.create(
        team=team,
        research_goal="invite flow",
        status=Study.Status.RECRUITING,
        target_completed_count=5,
    )
    InterviewGuide.objects.create(team=team, study=study, is_current=True, sections=[])
    link = StudyLink.objects.create(study=study, team=team, require_invitation=require_invitation)
    return team, study, link


def test_open_link_works_without_token():
    team, study, link = _boot(require_invitation=False)
    c = Client()
    r = c.get(f"/i/{link.slug}/")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_closed_link_rejects_missing_token():
    team, study, link = _boot(require_invitation=True)
    c = Client()
    r = c.get(f"/i/{link.slug}/")
    assert r.status_code == 403
    assert r.json()["error_code"] == "invitation_required"


def test_closed_link_rejects_invalid_token():
    team, study, link = _boot(require_invitation=True)
    c = Client()
    r = c.get(f"/i/{link.slug}/?t=nope")
    assert r.status_code == 403
    assert r.json()["error_code"] == "invitation_invalid"


def test_closed_link_accepts_valid_token_and_binds_participation():
    team, study, link = _boot(require_invitation=True)
    inv = Invitation.objects.create(
        team=team, study_link=link, recipient_hash="h1", recipient_display="a@x"
    )
    c = Client()
    r = c.get(f"/i/{link.slug}/?t={inv.token}")
    assert r.status_code == 200
    body = r.json()
    inv.refresh_from_db()
    assert inv.status == Invitation.Status.ACCEPTED
    assert str(inv.participation_id) == body["participation"]["id"]
    # trace_id alignment: participation.trace_id == invitation.trace_id
    p = Participation.objects.get(id=body["participation"]["id"])
    assert p.trace_id == inv.trace_id


def test_revoked_token_rejected():
    team, study, link = _boot(require_invitation=True)
    inv = Invitation.objects.create(
        team=team, study_link=link, recipient_hash="h2",
        status=Invitation.Status.REVOKED,
    )
    c = Client()
    r = c.get(f"/i/{link.slug}/?t={inv.token}")
    assert r.status_code == 403
    assert r.json()["error_code"] == "invitation_revoked"


def test_returning_invited_user_reuses_same_participation():
    team, study, link = _boot(require_invitation=True)
    inv = Invitation.objects.create(team=team, study_link=link, recipient_hash="h3")
    c = Client()
    r1 = c.get(f"/i/{link.slug}/?t={inv.token}")
    pid1 = r1.json()["participation"]["id"]
    # Fresh client (no cookie) — should still resolve via invitation binding.
    c2 = Client()
    r2 = c2.get(f"/i/{link.slug}/?t={inv.token}")
    pid2 = r2.json()["participation"]["id"]
    assert pid1 == pid2
