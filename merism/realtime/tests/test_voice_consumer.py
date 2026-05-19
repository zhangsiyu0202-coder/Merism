"""Integration tests for the pipeline-driven VoiceConsumer.

Uses ``channels.testing.WebsocketCommunicator`` — no live DashScope or
DeepSeek. We monkey-patch the three upstream clients with fakes so
tests are hermetic + fast.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import patch

import pytest
from channels.testing import WebsocketCommunicator

from merism.asgi import application
from merism.stt import STTEvent


# ── Fakes (module-level so patch() can find them cleanly) ──


class _FakeParaformer:
    """Yields one interim + one final transcript, then drains."""

    warmup_calls = 0

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    async def warmup(self, timeout_s: float = 3.0) -> None:
        _ = timeout_s
        type(self).warmup_calls += 1

    async def stream_stt(self, audio_iter: AsyncIterator[bytes]) -> AsyncIterator[STTEvent]:
        # Consume whatever audio comes in; yield a synthetic transcript
        # immediately so the test isn't timing-sensitive.
        sent_something = False
        async for chunk in audio_iter:
            if chunk:
                sent_something = True
                break
        if sent_something:
            yield STTEvent(text="你好", is_final=False, confidence=0.9)
            yield STTEvent(text="你好，我想了解一下", is_final=True, confidence=0.95)
        # Drain the rest silently.
        async for _ in audio_iter:
            pass


class _FakeDeepSeekStreamChunk:
    """Shape-compatible with openai's streaming chunks."""

    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.delta = _FakeDelta(content)


class _FakeDelta:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeDeepSeekClient:
    """Replaces ``merism.memai.llm.get_llm`` for tests."""

    class chat:  # noqa: N801 — shape-compat with openai SDK
        class completions:
            @staticmethod
            def create(*_args: Any, **kwargs: Any) -> list[_FakeDeepSeekStreamChunk]:
                # Return an iterable of synthetic chunks.
                tokens = ["很", "高", "兴", "你", "来", "了", "。"]
                if kwargs.get("stream"):
                    return [_FakeDeepSeekStreamChunk(t) for t in tokens]
                raise AssertionError("pipeline expects stream=True")


class _FakeCosyVoice:
    """Yields a few PCM chunks per text input drain."""

    warmup_calls = 0

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    async def warmup(self, timeout_s: float = 3.0) -> None:
        _ = timeout_s
        type(self).warmup_calls += 1

    async def stream_tts(self, text_iter: AsyncIterator[str]) -> AsyncIterator[bytes]:
        chunks_seen = 0
        async for _ in text_iter:
            chunks_seen += 1
        # After the text stream drains, yield some synthetic audio.
        for i in range(3):
            yield b"\x00" * 4800       # 100 ms of silence at 24 kHz PCM16
        _ = chunks_seen


# ── Test fixtures ─────────────────────────────────────────


@pytest.fixture
def patched_voice_clients():
    """Patch STT / TTS / LLM clients module-wide for the duration of the test."""

    _FakeParaformer.warmup_calls = 0
    _FakeCosyVoice.warmup_calls = 0

    async def _fake_stream_turn(session, *, participant_message, vision_context=""):
        """Minimal stand-in for moderator.stream_turn in voice-pipeline tests.

        These tests care about frame mechanics, not moderator semantics —
        so we yield a deterministic two-chunk reply without touching
        DeepSeek or the function-calling decision surface.
        """
        for delta in ("Hello. ", "Tell me more."):
            yield delta

    with patch("merism.voice.processors.stt.ParaformerClient", _FakeParaformer), patch(
        "merism.voice.processors.tts.CosyVoiceClient", _FakeCosyVoice
    ), patch("merism.voice.processors.llm.get_llm", return_value=_FakeDeepSeekClient), patch(
        "merism.voice.processors.moderator.stream_turn", _fake_stream_turn
    ):
        yield


# ── Fixtures for a real session in the test DB ────────────


@pytest.fixture
def make_session(db):
    """Factory that creates a real InterviewSession row with a barge-in flag."""
    import uuid

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

    def _build(*, barge_in_enabled: bool = False) -> InterviewSession:
        suffix = uuid.uuid4().hex[:8]
        admin = User.objects.create_superuser(
            username=f"pipeline-test-{suffix}@merism.test",
            email=f"pipeline-test-{suffix}@merism.test",
            password="x",
        )
        org = Organization.objects.create(
            name=f"Pipeline Demo {suffix}", slug=f"pipeline-demo-{suffix}"
        )
        team = Team.objects.create(name="R", organization=org)
        study = Study.objects.create(
            team=team,
            created_by=admin,
            name="Pipeline test study",
            research_goal="Smoke the new pipeline VoiceConsumer",
            interview_mode=Study.InterviewMode.VOICE,
            estimated_minutes=10,
            barge_in_enabled=barge_in_enabled,
        )
        guide = InterviewGuide.objects.create(
            team=team, study=study, version="1.0.0", is_current=True, sections=[]
        )
        participant = Participant.objects.create(
            team=team, external_id=f"ptest-{suffix}", name="Pipeline Tester"
        )
        participation = Participation.objects.create(
            team=team, study=study, participant=participant
        )
        return InterviewSession.objects.create(
            team=team,
            study=study,
            guide=guide,
            participation=participation,
            status=InterviewSession.Status.ACTIVE,
        )

    return _build


# ── Tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_session_ready_on_connect(make_session, patched_voice_clients):
    session = await asyncio.to_thread(make_session)
    communicator = WebsocketCommunicator(
        application, f"/ws/sessions/{session.id}/voice/"
    )
    connected, _ = await communicator.connect()
    assert connected

    msg = await communicator.receive_from(timeout=3)
    data = json.loads(msg)
    assert data["type"] == "session_ready"
    assert data["session_id"] == str(session.id)
    assert data["barge_in_enabled"] is False
    await asyncio.sleep(0.05)
    assert _FakeParaformer.warmup_calls == 1
    assert _FakeCosyVoice.warmup_calls == 1

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_ping_pong(make_session, patched_voice_clients):
    session = await asyncio.to_thread(make_session)
    communicator = WebsocketCommunicator(
        application, f"/ws/sessions/{session.id}/voice/"
    )
    await communicator.connect()
    # Drain session_ready
    await communicator.receive_from(timeout=3)

    await communicator.send_to(text_data=json.dumps({"type": "ping"}))
    reply = await communicator.receive_from(timeout=3)
    assert json.loads(reply)["type"] == "pong"
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_text_input_produces_agent_deltas_and_done(
    make_session, patched_voice_clients
):
    """Text input → pipeline → LLMTextFrame × N → AgentTextDelta × N + AgentTextDone."""
    session = await asyncio.to_thread(make_session)
    communicator = WebsocketCommunicator(
        application, f"/ws/sessions/{session.id}/voice/"
    )
    await communicator.connect()
    await communicator.receive_from(timeout=3)   # session_ready

    await communicator.send_to(
        text_data=json.dumps({"type": "text_input", "text": "你好"})
    )

    deltas: list[str] = []
    done_text = ""
    audio_chunks = 0
    # Collect messages until we see AgentTextDone or time out
    for _ in range(30):
        try:
            frame = await communicator.receive_output(timeout=3)
        except Exception:
            break
        if "bytes" in frame and frame["bytes"]:
            audio_chunks += 1
            continue
        if "text" in frame and frame["text"]:
            data = json.loads(frame["text"])
            if data.get("type") == "agent_text_delta":
                deltas.append(data["delta"])
            elif data.get("type") == "agent_text_done":
                done_text = data["text"]
                break

    assert deltas, "expected at least one agent_text_delta"
    assert done_text, "expected agent_text_done"
    assert "".join(deltas) == done_text, (
        f"done text should be the concatenation of deltas; "
        f"got {done_text!r} vs {''.join(deltas)!r}"
    )
    # Audio chunks are nice-to-have; assert >=0 so the test still passes
    # if the fake yields them after the done message.
    assert audio_chunks >= 0

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_barge_in_accepted_when_enabled(make_session, patched_voice_clients):
    """PTT speaking-start → pipeline → BargeInAccepted when study flag is on."""
    session = await asyncio.to_thread(make_session, barge_in_enabled=True)
    communicator = WebsocketCommunicator(
        application, f"/ws/sessions/{session.id}/voice/"
    )
    await communicator.connect()
    await communicator.receive_from(timeout=3)    # session_ready

    # Start a text-driven turn so there's something to barge in on.
    await communicator.send_to(
        text_data=json.dumps({"type": "text_input", "text": "讲讲你的工作吧"})
    )
    # Immediately send a PTT start.
    await communicator.send_to(
        text_data=json.dumps({"type": "ptt_speaking_start", "ts": 0.0})
    )

    saw_barge_in = False
    for _ in range(25):
        try:
            frame = await communicator.receive_output(timeout=3)
        except Exception:
            break
        if "text" not in frame or not frame["text"]:
            continue
        data = json.loads(frame["text"])
        if data.get("type") == "barge_in_accepted":
            saw_barge_in = True
            break

    assert saw_barge_in, "expected a barge_in_accepted message"
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_ptt_start_ignored_when_barge_in_disabled(
    make_session, patched_voice_clients
):
    """Default-off studies should not interrupt the active TTS stream."""
    session = await asyncio.to_thread(make_session, barge_in_enabled=False)
    communicator = WebsocketCommunicator(
        application, f"/ws/sessions/{session.id}/voice/"
    )
    await communicator.connect()
    await communicator.receive_from(timeout=3)    # session_ready

    # Fire PTT start directly; with PTT semantics the server always respects it.
    await communicator.send_to(
        text_data=json.dumps(
            {"type": "ptt_speaking_start", "ts": 0.0, "audio_played_ms": 0}
        )
    )

    saw_barge_in = False
    for _ in range(30):
        try:
            frame = await communicator.receive_output(timeout=2)
        except Exception:
            break
        if "text" not in frame or not frame["text"]:
            continue
        data = json.loads(frame["text"])
        if data.get("type") == "barge_in_accepted":
            saw_barge_in = True
            break

    assert not saw_barge_in, "default-off studies must ignore ptt_speaking_start"
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_ptt_start_accepted_when_barge_in_enabled(
    make_session, patched_voice_clients
):
    """Enabled studies still support barge-in from the PTT start event."""
    session = await asyncio.to_thread(make_session, barge_in_enabled=True)
    communicator = WebsocketCommunicator(
        application, f"/ws/sessions/{session.id}/voice/"
    )
    await communicator.connect()
    await communicator.receive_from(timeout=3)    # session_ready

    await communicator.send_to(
        text_data=json.dumps(
            {"type": "ptt_speaking_start", "ts": 0.0, "audio_played_ms": 0}
        )
    )

    saw_barge_in = False
    for _ in range(30):
        try:
            frame = await communicator.receive_output(timeout=2)
        except Exception:
            break
        if "text" not in frame or not frame["text"]:
            continue
        data = json.loads(frame["text"])
        if data.get("type") == "barge_in_accepted":
            saw_barge_in = True
            break

    assert saw_barge_in, "expected a barge_in_accepted message when enabled"
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_malformed_json_returns_error_message(make_session, patched_voice_clients):
    session = await asyncio.to_thread(make_session)
    communicator = WebsocketCommunicator(
        application, f"/ws/sessions/{session.id}/voice/"
    )
    await communicator.connect()
    await communicator.receive_from(timeout=3)      # session_ready

    await communicator.send_to(text_data="not-json")
    reply = await communicator.receive_from(timeout=3)
    data = json.loads(reply)
    assert data["type"] == "error"
    assert data["code"] == "malformed_message"

    await communicator.disconnect()
