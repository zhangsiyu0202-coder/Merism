"""V3 voice consumer integration test — WebSocket end-to-end.

Verifies VoiceConsumer routes v3 sessions to ModeratorProcessor and the
v3 graph drives questions out the pipeline in real time.

Uses ``off`` mode questions so no LLM call is made between turns; the
test is deterministic and fast.
"""
# pyright: reportTypedDictNotRequiredAccess=false

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import patch

import pytest
from channels.testing import WebsocketCommunicator

from merism.asgi import application
from merism.stt import STTEvent


class _FakeParaformer:
    warmup_calls = 0

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    async def warmup(self, timeout_s: float = 3.0) -> None:
        type(self).warmup_calls += 1

    async def stream_stt(self, audio_iter: AsyncIterator[bytes]) -> AsyncIterator[STTEvent]:
        async for _ in audio_iter:
            pass
        if False:
            yield STTEvent(text="", is_final=True, confidence=0.0)


class _FakeCosyVoice:
    warmup_calls = 0

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    async def warmup(self, timeout_s: float = 3.0) -> None:
        type(self).warmup_calls += 1

    async def stream_tts(self, text_iter: AsyncIterator[str]) -> AsyncIterator[bytes]:
        async for _ in text_iter:
            pass
        for _ in range(3):
            yield b"\x00" * 4800


@pytest.fixture
def patched_voice():
    """Patch STT / TTS for v3 voice tests. v3 off-mode doesn't call any LLM."""
    from merism.conductor.factory import reset_graph_cache

    _FakeParaformer.warmup_calls = 0
    _FakeCosyVoice.warmup_calls = 0
    reset_graph_cache()
    with (
        patch("merism.voice.processors.stt.ParaformerClient", _FakeParaformer),
        patch("merism.voice.processors.tts.CosyVoiceClient", _FakeCosyVoice),
    ):
        yield
    reset_graph_cache()


@pytest.fixture
def make_session(db):
    """Create a real InterviewSession with a v3 outline (off mode)."""
    from django.contrib.auth import get_user_model

    from merism.models import (
        InterviewGuide,
        InterviewSession,
        Organization,
        Participant,
        Participation,
        Study,
        Team,
    )

    User = get_user_model()

    def _build() -> InterviewSession:
        suffix = uuid.uuid4().hex[:8]
        admin = User.objects.create_superuser(
            username=f"v3voice-test-{suffix}@merism.test",
            email=f"v3voice-test-{suffix}@merism.test",
            password="x",
        )
        org = Organization.objects.create(name=f"V3Voice {suffix}", slug=f"v3voice-{suffix}")
        team = Team.objects.create(name="R", organization=org)
        study = Study.objects.create(
            team=team,
            created_by=admin,
            name="V3 voice test",
            research_goal="Verify v3 voice routing",
            interview_mode=Study.InterviewMode.VOICE,
            estimated_minutes=10,
        )
        guide = InterviewGuide.objects.create(
            team=team,
            study=study,
            version="3.0.0",
            is_current=True,
            sections={
                "version": "v3",
                "sections": [
                    {
                        "id": "s1",
                        "title": "Test",
                        "questions": [
                            {
                                "id": "q1",
                                "ask": "Hello, what do you do?",
                                "follow_up_mode": "off",
                                "probe_instruction": None,
                            },
                        ],
                    },
                ],
            },
        )
        participant = Participant.objects.create(team=team, external_id=f"v3vp-{suffix}", name="V3 Voice Tester")
        participation = Participation.objects.create(team=team, study=study, participant=participant)
        return InterviewSession.objects.create(
            team=team,
            study=study,
            guide=guide,
            guide_snapshot=guide.sections,
            participation=participation,
            status=InterviewSession.Status.ACTIVE,
            mode=InterviewSession.Mode.VOICE,
        )

    return _build


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_session_ready_on_connect(make_session: Any, patched_voice: Any) -> None:
    """v3 session connects, session_ready emitted (consumer routes to v3 path)."""
    session = await asyncio.to_thread(make_session)
    communicator = WebsocketCommunicator(application, f"/ws/sessions/{session.id}/voice/")
    connected, _ = await communicator.connect()
    assert connected

    msg = await communicator.receive_from(timeout=5)
    data = json.loads(msg)
    assert data["type"] == "session_ready"
    assert data["session_id"] == str(session.id)

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_first_question_emitted_on_bootstrap(make_session: Any, patched_voice: Any) -> None:
    """Bootstrap should call start_interview and push the first question's
    text downstream as agent_text_delta + agent_text_done."""
    session = await asyncio.to_thread(make_session)
    communicator = WebsocketCommunicator(application, f"/ws/sessions/{session.id}/voice/")
    await communicator.connect()
    await communicator.receive_from(timeout=5)  # session_ready

    deltas: list[str] = []
    done_text = ""
    for _ in range(50):
        try:
            frame = await communicator.receive_output(timeout=5)
        except Exception:
            break
        if "text" not in frame or not frame["text"]:
            continue
        data = json.loads(frame["text"])
        if data.get("type") == "agent_text_delta":
            deltas.append(data["delta"])
        elif data.get("type") == "agent_text_done":
            done_text = data["text"]
            break

    assert done_text, f"expected agent_text_done with bootstrap question; got deltas={deltas}"
    assert "what do you do" in done_text.lower(), f"expected first v3 question text; got {done_text!r}"

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_bootstrap_prefers_snapshot_over_live_guide(make_session: Any, patched_voice: Any) -> None:
    """If guide_snapshot diverges from the live guide, voice should use the snapshot."""
    from asgiref.sync import sync_to_async

    session = await asyncio.to_thread(make_session)
    snapshot_outline = {
        "version": "v3",
        "sections": [
            {
                "id": "s1",
                "title": "Snapshot",
                "questions": [
                    {
                        "id": "q1",
                        "ask": "SNAPSHOT: how do you spend your day?",
                        "follow_up_mode": "off",
                        "probe_instruction": None,
                    }
                ],
            }
        ],
    }

    await sync_to_async(lambda: type(session).objects.filter(id=session.id).update(guide_snapshot=snapshot_outline))()
    await sync_to_async(session.refresh_from_db)()

    communicator = WebsocketCommunicator(application, f"/ws/sessions/{session.id}/voice/")
    await communicator.connect()
    await communicator.receive_from(timeout=5)  # session_ready

    done_text = ""
    for _ in range(50):
        try:
            frame = await communicator.receive_output(timeout=5)
        except Exception:
            break
        if "text" not in frame or not frame["text"]:
            continue
        data = json.loads(frame["text"])
        if data.get("type") == "agent_text_done":
            done_text = data["text"]
            break

    assert "snapshot" in done_text.lower()
    assert "live" not in done_text.lower()

    await communicator.disconnect()
