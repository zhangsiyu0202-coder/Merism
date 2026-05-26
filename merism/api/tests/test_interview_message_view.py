"""HTTP text-mode endpoint wraps the v3 LangGraph engine as SSE.

Patches the v3 graph factory so we don't actually call DeepSeek; verifies
the endpoint streams ``delta`` + ``done`` events and that v3 routing kicks in.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from django.test.client import Client

from merism.models import (
    InterviewGuide,
    InterviewSession,
    Organization,
    Participant,
    Participation,
    Study,
    Team,
)

pytestmark = pytest.mark.django_db(transaction=True)


def _boot():
    """Create a v3 session with a 1-question outline."""
    org = Organization.objects.create(name="Msg", slug=f"msg-{uuid.uuid4().hex[:6]}")
    team = Team.objects.create(organization=org, name="MT")
    study = Study.objects.create(team=team, research_goal="text mode", interview_mode="text")
    guide = InterviewGuide.objects.create(
        team=team,
        study=study,
        is_current=True,
        sections={
            "version": "v3",
            "sections": [
                {
                    "id": "s1",
                    "title": "W",
                    "questions": [
                        {
                            "id": "q1",
                            "ask": "What do you do?",
                            "follow_up_mode": "off",
                            "probe_instruction": None,
                        }
                    ],
                }
            ],
        },
    )
    participant = Participant.objects.create(team=team)
    p = Participation.objects.create(study=study, team=team, participant=participant)
    s = InterviewSession.objects.create(
        team=team,
        study=study,
        participation=p,
        guide=guide,
        trace_id=p.trace_id,
        follow_up_mode="off",
    )
    return p, s


def _patch_runner(monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any] | None = None) -> None:
    """Patch ``run_turn`` so the test doesn't hit the real graph / LLM."""
    payload = payload or {
        "kind": "question",
        "question": "What do you do?",
        "section_id": "s1",
        "question_id": "q1",
        "turn_kind": "main",
        "error": None,
    }

    async def _fake(**kwargs):
        return payload

    monkeypatch.setattr("merism.conductor.text_adapter.run_turn", _fake)


def test_message_endpoint_requires_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    _p, s = _boot()
    _patch_runner(monkeypatch)
    c = Client()
    r = c.post(
        f"/api/sessions/{s.id}/message/",
        data=json.dumps({"message": "hi"}),
        content_type="application/json",
    )
    assert r.status_code == 403


def test_message_endpoint_streams_delta_and_done(monkeypatch: pytest.MonkeyPatch) -> None:
    p, s = _boot()
    _patch_runner(
        monkeypatch,
        payload={
            "kind": "question",
            "question": "What do you do?",
            "section_id": "s1",
            "question_id": "q1",
            "turn_kind": "main",
            "error": None,
        },
    )
    c = Client()
    c.cookies["merism_browser_token"] = str(p.browser_token)
    r = c.post(
        f"/api/sessions/{s.id}/message/",
        data=json.dumps({"message": "hello"}),
        content_type="application/json",
    )
    assert r.status_code == 200
    body = b"".join(r.streaming_content).decode()
    assert "event: delta" in body
    assert "event: done" in body
    assert "What do you do?" in body


def test_message_endpoint_404_for_unknown_session(monkeypatch: pytest.MonkeyPatch) -> None:
    _p, _s = _boot()
    c = Client()
    bogus = uuid.uuid4()
    r = c.post(
        f"/api/sessions/{bogus}/message/",
        data=json.dumps({"message": "hi"}),
        content_type="application/json",
    )
    assert r.status_code == 404
