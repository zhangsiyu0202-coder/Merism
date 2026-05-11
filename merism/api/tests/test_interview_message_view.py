"""HTTP text-mode endpoint wraps stream_turn as SSE.

Patches the LLM Gateway client (``merism.conductor.moderator.get_client``)
with a fake that serves both the decision (complete) and the generation
(stream) phases of the 2-node voice moderator.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from django.test.client import Client

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


pytestmark = pytest.mark.django_db(transaction=True)


def _boot():
    org = Organization.objects.create(name="Msg", slug=f"msg-{uuid.uuid4().hex[:6]}")
    team = Team.objects.create(organization=org, name="MT")
    study = Study.objects.create(team=team, research_goal="text mode", interview_mode="text")
    guide = InterviewGuide.objects.create(
        team=team, study=study, is_current=True,
        sections=[{"id": "s1", "title": "W", "scope": "global", "questions": [
            {"id": "q1", "text": "Go.", "probe_policy": "light", "max_probes": 2},
        ]}],
    )
    participant = Participant.objects.create(team=team)
    p = Participation.objects.create(study=study, team=team, participant=participant)
    s = InterviewSession.objects.create(
        team=team, study=study, participation=p, guide=guide, trace_id=p.trace_id,
        moderator_state={"current_section_id": "s1", "current_question_id": "q1", "phase": "active"},
    )
    return p, s


class _FakeGatewayClient:
    """Serves both complete() (decision) + stream() (generation)."""

    def __init__(self, decision: dict, reply_text: str):
        self._decision = decision
        self._reply_text = reply_text

    async def complete(self, **kwargs):
        message = SimpleNamespace(content=json.dumps(self._decision))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    async def stream(self, **kwargs):
        mid = len(self._reply_text) // 2
        for chunk_text in [self._reply_text[:mid], self._reply_text[mid:]]:
            delta = SimpleNamespace(content=chunk_text, tool_calls=None)
            yield SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=None, index=0)])


def _patch_gateway(monkeypatch, decision=None, text="hi there"):
    decision = decision or {"next_action": "followup", "probe_type": "expansion", "probe_triggered_by": "short"}
    fake = _FakeGatewayClient(decision=decision, reply_text=text)
    monkeypatch.setattr("merism.conductor.moderator.get_client", AsyncMock(return_value=fake))


def test_message_endpoint_requires_cookie(monkeypatch):
    p, s = _boot()
    _patch_gateway(monkeypatch)
    c = Client()
    r = c.post(f"/api/sessions/{s.id}/message/", data=json.dumps({"message": "hi"}), content_type="application/json")
    assert r.status_code == 403


def test_message_endpoint_streams_delta_and_done(monkeypatch):
    p, s = _boot()
    _patch_gateway(monkeypatch, text="Thanks.")
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

    kinds = list(SessionEvent.objects.filter(session=s).order_by("seq").values_list("kind", flat=True))
    assert kinds[:2] == ["user_turn", "model_reply"]


def test_message_endpoint_404_for_unknown_session(monkeypatch):
    _patch_gateway(monkeypatch)
    c = Client()
    r = c.post(
        f"/api/sessions/{uuid.uuid4()}/message/",
        data=json.dumps({"message": "x"}),
        content_type="application/json",
    )
    assert r.status_code == 404
