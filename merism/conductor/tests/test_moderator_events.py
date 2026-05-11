"""End-to-end moderator → SessionEvent logging.

Mocks the LLM client so we don't need network. Verifies:
- each turn appends user_turn + model_reply + decision events
- trace_id is carried onto the events
- max_probes hard cap holds (via existing decision_validator)
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

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


class _FakeStream:
    """Async iterator matching OpenAI's streaming response shape.

    Emits:
      - Two content deltas that concatenate to ``assistant_text``
      - One tool_call delta carrying the full function arguments JSON
    """

    def __init__(self, assistant_text: str, tool_args: dict):
        self._emitted = 0
        self._text = assistant_text
        self._tool_args = json.dumps(tool_args)

    def __aiter__(self):
        return self

    async def __anext__(self):
        self._emitted += 1
        if self._emitted == 1:
            return _delta_chunk(content=self._text[: len(self._text) // 2])
        if self._emitted == 2:
            return _delta_chunk(content=self._text[len(self._text) // 2 :])
        if self._emitted == 3:
            return _delta_chunk(tool_call_args=self._tool_args)
        raise StopAsyncIteration


def _delta_chunk(content: str | None = None, tool_call_args: str | None = None):
    tool_calls = []
    if tool_call_args is not None:
        tool_calls = [
            SimpleNamespace(
                function=SimpleNamespace(name="submit_next_action", arguments=tool_call_args)
            )
        ]
    delta = SimpleNamespace(content=content, tool_calls=tool_calls or None)
    choice = SimpleNamespace(delta=delta, finish_reason=None, index=0)
    return SimpleNamespace(choices=[choice])


class _FakeCompletions:
    def __init__(self, stream: _FakeStream):
        self._stream = stream

    async def create(self, **kwargs):
        return self._stream


class _FakeLLM:
    def __init__(self, assistant_text: str, tool_args: dict):
        self.chat = SimpleNamespace(
            completions=_FakeCompletions(_FakeStream(assistant_text, tool_args))
        )


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

    def _fake_llm_factory(**kw):
        return _FakeLLM(
            assistant_text="Thanks for sharing.",
            tool_args={"next_action": "move_on", "next_question_id": "q2"},
        )

    monkeypatch.setattr("merism.conductor.moderator.get_llm", _fake_llm_factory)

    from merism.conductor.moderator import stream_turn

    # Reload session with FKs
    session = await sync_to_async(
        lambda: type(session).objects.select_related("study", "guide").get(id=session.id)
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
    # Payload shape
    assert events[0].payload["text"] == "I use it daily."
    assert events[1].payload["text"] == "Thanks for sharing."
    assert events[2].payload["decision"]["next_action"] == "move_on"
    # trace_id propagated
    assert all(e.trace_id == session.trace_id for e in events)


@pytest.mark.asyncio
async def test_stream_turn_max_probes_forces_move_on(monkeypatch):
    """LLM says 'followup' but probes_done >= max_probes → validator overrides."""
    from asgiref.sync import sync_to_async

    session = await sync_to_async(_boot_session)()
    # Pre-load state as having already used all 2 probes on q1
    session.moderator_state = {
        "current_section_id": "s1",
        "current_question_id": "q1",
        "phase": "active",
        "followups_used": {"q1": {"asked": 2, "budget": 2}},
    }
    await sync_to_async(session.save)(update_fields=["moderator_state"])

    def _fake_llm_factory(**kw):
        return _FakeLLM(
            assistant_text="Go on.",
            tool_args={"next_action": "followup"},
        )

    monkeypatch.setattr("merism.conductor.moderator.get_llm", _fake_llm_factory)

    from merism.conductor.moderator import stream_turn

    session = await sync_to_async(
        lambda: type(session).objects.select_related("study", "guide").get(id=session.id)
    )()

    async for _ in stream_turn(session, participant_message="and then"):
        pass

    events = await sync_to_async(
        lambda: list(SessionEvent.objects.filter(session=session).order_by("seq"))
    )()
    decision_event = [e for e in events if e.kind == "decision"][-1]
    assert decision_event.payload["validator_overridden"] is True
