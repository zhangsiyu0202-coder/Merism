"""HTTP text-mode endpoint wraps stream_turn as SSE."""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

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


def _fake_llm_factory(text="hi there", args=None, **kw):
    args = args or {"next_action": "followup"}

    class _FakeStream:
        def __init__(self):
            self._n = 0
        def __aiter__(self):
            return self
        async def __anext__(self):
            self._n += 1
            if self._n == 1:
                return _delta(content=text)
            if self._n == 2:
                return _delta(tool_args=json.dumps(args))
            raise StopAsyncIteration

    def _delta(content=None, tool_args=None):
        tool_calls = None
        if tool_args:
            tool_calls = [SimpleNamespace(function=SimpleNamespace(name="submit_next_action", arguments=tool_args))]
        delta = SimpleNamespace(content=content, tool_calls=tool_calls)
        return SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=None, index=0)])

    class _Completions:
        async def create(self, **kwargs):
            return _FakeStream()

    return SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))


def test_message_endpoint_requires_cookie(monkeypatch):
    p, s = _boot()
    monkeypatch.setattr("merism.conductor.moderator.get_llm", _fake_llm_factory)
    c = Client()
    r = c.post(f"/api/sessions/{s.id}/message/", data=json.dumps({"message": "hi"}), content_type="application/json")
    assert r.status_code == 403


def test_message_endpoint_streams_delta_and_done(monkeypatch):
    p, s = _boot()
    monkeypatch.setattr("merism.conductor.moderator.get_llm", _fake_llm_factory)

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
    monkeypatch.setattr("merism.conductor.moderator.get_llm", _fake_llm_factory)
    c = Client()
    r = c.post(
        f"/api/sessions/{uuid.uuid4()}/message/",
        data=json.dumps({"message": "x"}),
        content_type="application/json",
    )
    assert r.status_code == 404
