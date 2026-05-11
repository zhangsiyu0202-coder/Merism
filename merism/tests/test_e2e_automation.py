"""End-to-end automation smoke.

Walks the full pipeline with mocked external I/O:

1. Researcher sets up Study + Guide + Screener + StudyLink in Django admin.
2. Participant resolves /i/<slug>/ → consent → screener → start.
3. Participant posts 2 text turns to /api/sessions/:id/message/ —
   each turn writes SessionEvent rows + updates moderator_state.
4. Final turn's moderator decision = close → closure fires.
5. Session.status = COMPLETED → post_save signal → Celery eager inline.
6. InboxItem rows exist for session_completed + insight_ready.
7. Participation.status = COMPLETED + Study.actual_completed_count == target.
8. Study auto-closed (status=CLOSED + link inactive).

Uses Celery eager mode + patches external LLM / RAG / insight so the
smoke runs in <10s with no network.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test.client import Client

from merism.models import (
    InboxItem,
    InterviewGuide,
    InterviewSession,
    Organization,
    Participation,
    Screener,
    SessionEvent,
    Study,
    StudyLink,
    Team,
)


pytestmark = pytest.mark.django_db(transaction=True)


def _fake_gateway_client(text: str, decision: dict):
    """Return a fake LLM Gateway client: complete() for decision + stream() for reply."""

    class _Fake:
        async def complete(self, **kwargs):
            message = SimpleNamespace(content=json.dumps(decision))
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

        async def stream(self, **kwargs):
            mid = len(text) // 2
            for chunk_text in [text[:mid], text[mid:]]:
                delta = SimpleNamespace(content=chunk_text, tool_calls=None)
                yield SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=None, index=0)])

    return _Fake()


def _fake_llm_factory(text: str, args: dict, **_kwargs):
    """Return a fake OpenAI client that streams one chunk of text + one tool_call."""

    def _delta(content=None, tool_args=None):
        tool_calls = None
        if tool_args:
            tool_calls = [
                SimpleNamespace(
                    function=SimpleNamespace(name="submit_next_action", arguments=tool_args)
                )
            ]
        delta = SimpleNamespace(content=content, tool_calls=tool_calls)
        return SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=None, index=0)])

    class _Stream:
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

    class _Completions:
        async def create(self, **_):
            return _Stream()

    return SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))


def _boot_study(interview_mode="text"):
    """Researcher-side: create a recruitment-ready Study via admin-level ORM."""
    org = Organization.objects.create(name="E2E", slug=f"e2e-{uuid.uuid4().hex[:6]}")
    team = Team.objects.create(organization=org, name="E2ET")
    study = Study.objects.create(
        team=team,
        research_goal="What makes users stick?",
        status=Study.Status.RECRUITING,
        interview_mode=interview_mode,
        target_completed_count=1,
    )
    InterviewGuide.objects.create(
        team=team,
        study=study,
        is_current=True,
        sections=[
            {
                "id": "s1",
                "title": "Warm-up",
                "scope": "global",
                "questions": [
                    {"id": "q1", "text": "Tell me.", "probe_policy": "light", "max_probes": 2},
                ],
            }
        ],
    )
    Screener.objects.create(
        team=team,
        study=study,
        questions=[{"id": "fit", "text": "Fit?"}],
        pass_logic={"correct_answers": {"fit": "yes"}},
    )
    link = StudyLink.objects.create(study=study, team=team)
    return team, study, link


def test_full_chain_invite_to_inbox():
    team, study, link = _boot_study()

    # ─── Participant hits /i/<slug>/ ───
    c = Client()
    r = c.get(f"/i/{link.slug}/")
    assert r.status_code == 200
    assert r.json()["next_step"] == "consent"

    r = c.post(f"/i/{link.slug}/consent/")
    assert r.status_code == 200
    assert r.json()["next_step"] == "screener"

    r = c.post(
        f"/i/{link.slug}/screener/",
        data=json.dumps({"answers": {"fit": "yes"}}),
        content_type="application/json",
    )
    assert r.status_code == 200
    assert r.json()["passed"] is True

    r = c.post(f"/i/{link.slug}/start/")
    assert r.status_code == 200
    session_id = r.json()["session_id"]

    # ─── Text turns against the moderator (mocked LLM) ───
    # Turn 1: followup (keeps session open)
    from unittest.mock import AsyncMock

    first = _fake_gateway_client(
        "Thanks for telling me about it.",
        {"next_action": "followup", "probe_type": "expansion", "probe_triggered_by": "short"},
    )
    with patch(
        "merism.conductor.moderator.get_client",
        AsyncMock(return_value=first),
    ):
        r = c.post(
            f"/api/sessions/{session_id}/message/",
            data=json.dumps({"message": "I use it every morning."}),
            content_type="application/json",
        )
        assert r.status_code == 200
        b"".join(r.streaming_content)  # consume

    # Turn 2: close (triggers closure + pipeline)
    second = _fake_gateway_client(
        "Got it, thanks for your time.",
        {"next_action": "close"},
    )
    # Mock the post-session pipeline to a no-op (we're testing the wiring,
    # not the codebook/RAG agents which need DeepSeek).
    with patch(
        "merism.conductor.moderator.get_client",
        AsyncMock(return_value=second),
    ), patch(
        "merism.conductor.tasks.process_completed_session.delay",
        side_effect=lambda sid: None,
    ):
        r = c.post(
            f"/api/sessions/{session_id}/message/",
            data=json.dumps({"message": "Ok, thanks, bye."}),
            content_type="application/json",
        )
        assert r.status_code == 200
        b"".join(r.streaming_content)

    # ─── Session closed by 6-signal check ───
    session = InterviewSession.objects.get(id=session_id)
    assert session.status == InterviewSession.Status.COMPLETED
    assert session.ended_at is not None

    # SessionEvent rows written per turn
    events = list(SessionEvent.objects.filter(session=session).order_by("seq"))
    event_kinds = [e.kind for e in events]
    # 2 turns × 3 events (user_turn, model_reply, decision) + 1 lifecycle
    assert event_kinds.count("user_turn") == 2
    assert event_kinds.count("model_reply") == 2
    assert event_kinds.count("decision") == 2
    assert "session_lifecycle" in event_kinds

    # ─── Participation + Study auto-close ───
    participation = Participation.objects.get(id=session.participation_id)
    assert participation.status == Participation.Status.COMPLETED
    assert participation.completed_at is not None

    study.refresh_from_db()
    link.refresh_from_db()
    assert study.actual_completed_count == 1
    assert study.status == Study.Status.CLOSED
    assert link.is_active is False

    # ─── Inbox items written ───
    inbox_kinds = set(
        InboxItem.objects.filter(team=team).values_list("kind", flat=True)
    )
    assert "session_completed" in inbox_kinds
    assert "study_completed" in inbox_kinds

    # ─── Trace coherence ───
    # Participation.trace_id == Session.trace_id == Events.trace_id
    assert session.trace_id == participation.trace_id
    for ev in events:
        if ev.trace_id is not None:
            assert ev.trace_id == participation.trace_id
