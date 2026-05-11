"""End-to-end moderator → SessionEvent logging, for the 2-node voice pipeline.

Verifies the coverage_steer → generate flow:
- each turn appends user_turn + model_reply + decision events
- trace_id is carried onto the events
- max_probes hard cap holds (via decision_validator overriding the LLM)

Mocks the LLM Gateway client's ``complete()`` (decision phase) and
``stream()`` (generation phase) so no network is needed.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

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


def _fake_complete_response(decision_payload: dict) -> SimpleNamespace:
    """Build the shape returned by LiteLLMClient.complete()."""
    message = SimpleNamespace(content=json.dumps(decision_payload))
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class _FakeStream:
    """Async iterator for LiteLLMClient.stream() — yields text chunks only."""

    def __init__(self, text: str):
        self._text = text
        self._emitted = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        self._emitted += 1
        if self._emitted == 1:
            return _delta_chunk(self._text[: len(self._text) // 2])
        if self._emitted == 2:
            return _delta_chunk(self._text[len(self._text) // 2 :])
        raise StopAsyncIteration


def _delta_chunk(content: str):
    delta = SimpleNamespace(content=content, tool_calls=None)
    choice = SimpleNamespace(delta=delta, finish_reason=None, index=0)
    return SimpleNamespace(choices=[choice])


class _FakeGatewayClient:
    """Stands in for LiteLLMClient. Exposes complete() + stream()."""

    def __init__(self, *, decision: dict, reply_text: str):
        self._decision = decision
        self._reply_text = reply_text

    async def complete(self, **kwargs):
        return _fake_complete_response(self._decision)

    async def stream(self, **kwargs):
        # Must be an async generator directly (not a coroutine returning one)
        stream = _FakeStream(self._reply_text)
        async for chunk in stream:
            yield chunk


def _boot_session():
    org = Organization.objects.create(name="Mod", slug=f"mod-{uuid.uuid4().hex[:6]}")
    team = Team.objects.create(organization=org, name="MT")
    study = Study.objects.create(team=team, research_goal="test moderator events")
    guide = InterviewGuide.objects.create(
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
                    {"id": "q2", "text": "And then?", "probe_policy": "light", "max_probes": 2},
                ],
            }
        ],
    )
    participant = Participant.objects.create(team=team)
    p = Participation.objects.create(study=study, team=team, participant=participant)
    return InterviewSession.objects.create(
        team=team,
        study=study,
        participation=p,
        guide=guide,
        trace_id=p.trace_id,
        moderator_state={"current_section_id": "s1", "current_question_id": "q1", "phase": "active"},
    )


@pytest.mark.asyncio
async def test_stream_turn_logs_events_per_turn(monkeypatch):
    from asgiref.sync import sync_to_async

    session = await sync_to_async(_boot_session)()

    fake_client = _FakeGatewayClient(
        decision={"next_action": "move_on", "next_question_id": "q2"},
        reply_text="Thanks for sharing.",
    )
    # Patch get_client to always return our fake (for both decision + generate)
    async_mock = AsyncMock(return_value=fake_client)
    monkeypatch.setattr("merism.conductor.moderator.get_client", async_mock)

    from merism.conductor.moderator import stream_turn

    session = await sync_to_async(
        lambda: type(session).objects.select_related("study__team", "guide").get(id=session.id)
    )()

    chunks: list[str] = []
    async for delta in stream_turn(session, participant_message="I use it daily."):
        chunks.append(delta)

    assistant_text = "".join(chunks)
    assert assistant_text == "Thanks for sharing."

    events = await sync_to_async(
        lambda: list(SessionEvent.objects.filter(session=session).order_by("seq"))
    )()
    kinds = [e.kind for e in events]
    assert kinds == ["user_turn", "model_reply", "decision"]
    assert events[0].payload["text"] == "I use it daily."
    assert events[1].payload["text"] == "Thanks for sharing."
    assert events[2].payload["decision"]["next_action"] == "move_on"
    assert all(e.trace_id == session.trace_id for e in events)


@pytest.mark.asyncio
async def test_stream_turn_max_probes_forces_move_on(monkeypatch):
    """LLM says 'followup' but probes_done >= max_probes → validator overrides."""
    from asgiref.sync import sync_to_async

    session = await sync_to_async(_boot_session)()
    session.moderator_state = {
        "current_section_id": "s1",
        "current_question_id": "q1",
        "phase": "active",
        "followups_used": {"q1": {"asked": 2, "budget": 2}},
    }
    await sync_to_async(session.save)(update_fields=["moderator_state"])

    fake_client = _FakeGatewayClient(
        decision={"next_action": "followup", "probe_type": "expansion", "probe_triggered_by": "vague"},
        reply_text="Go on.",
    )
    async_mock = AsyncMock(return_value=fake_client)
    monkeypatch.setattr("merism.conductor.moderator.get_client", async_mock)

    from merism.conductor.moderator import stream_turn

    session = await sync_to_async(
        lambda: type(session).objects.select_related("study__team", "guide").get(id=session.id)
    )()

    async for _ in stream_turn(session, participant_message="and then"):
        pass

    events = await sync_to_async(
        lambda: list(SessionEvent.objects.filter(session=session).order_by("seq"))
    )()
    decision_event = [e for e in events if e.kind == "decision"][-1]
    assert decision_event.payload["validator_overridden"] is True
