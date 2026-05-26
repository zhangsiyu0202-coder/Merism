"""TranscriptRecorder observer — frame-deduplication contract.

Bug context (2026-05-24): the observer fires once per ``push_frame``
call along the pipeline, NOT once per frame. With Moderator → TTS →
ConvState as the post-LLM chain, a single ``LLMTextFrame`` traversed 3
``push_frame`` boundaries, so without dedup the recorder appended the
text 3 times — every assistant turn ended up containing its own text
repeated 3 times verbatim. Fix: gate ``on_frame`` on ``dst is None``
(terminal observation only).
"""

from __future__ import annotations

import pytest

from merism.voice.frames import (
    BotStoppedSpeakingFrame,
    LLMTextFrame,
    TranscriptionFrame,
)
from merism.voice.observer import TranscriptRecorder


class _FakeDirection:
    DOWNSTREAM = "downstream"


class _FakeProcessor:
    """Stand-in for FrameProcessor. The recorder only reads identity."""

    def __init__(self, name: str) -> None:
        self.name = name


@pytest.mark.asyncio
class TestTranscriptRecorderDedupe:
    async def test_text_recorded_once_when_observed_at_each_hop(self) -> None:
        """Pipecat's pipeline fires the observer at every push_frame.

        Replay a frame's full traversal: Moderator → TTS, TTS → ConvState,
        ConvState → None (terminal). The recorder must count it exactly
        once — namely at the terminal observation.
        """
        recorder = TranscriptRecorder()
        moderator = _FakeProcessor("moderator")
        tts = _FakeProcessor("tts")
        conv_state = _FakeProcessor("conv_state")

        text_frame = LLMTextFrame(text="X")
        # The same frame fires the observer at each hop:
        await recorder.on_frame(text_frame, moderator, tts, _FakeDirection.DOWNSTREAM)
        await recorder.on_frame(text_frame, tts, conv_state, _FakeDirection.DOWNSTREAM)
        await recorder.on_frame(text_frame, conv_state, None, _FakeDirection.DOWNSTREAM)

        await recorder.on_frame(
            BotStoppedSpeakingFrame(),
            conv_state,
            None,
            _FakeDirection.DOWNSTREAM,
        )

        turns = recorder.drain()
        assert len(turns) == 1
        assert turns[0]["role"] == "assistant"
        # The decisive assertion: the text is NOT triplicated.
        assert turns[0]["text"] == "X"

    async def test_user_transcription_not_duplicated(self) -> None:
        """Same dedup contract applies to ``TranscriptionFrame`` from STT."""
        recorder = TranscriptRecorder()
        stt = _FakeProcessor("stt")
        moderator = _FakeProcessor("moderator")
        tts = _FakeProcessor("tts")
        conv_state = _FakeProcessor("conv_state")

        frame = TranscriptionFrame(text="hello")
        # Traverses STT → Moderator → TTS → ConvState → None.
        await recorder.on_frame(frame, stt, moderator, _FakeDirection.DOWNSTREAM)
        await recorder.on_frame(frame, moderator, tts, _FakeDirection.DOWNSTREAM)
        await recorder.on_frame(frame, tts, conv_state, _FakeDirection.DOWNSTREAM)
        await recorder.on_frame(frame, conv_state, None, _FakeDirection.DOWNSTREAM)

        await recorder.on_frame(
            BotStoppedSpeakingFrame(),
            conv_state,
            None,
            _FakeDirection.DOWNSTREAM,
        )

        turns = recorder.drain()
        # One user turn (the assistant turn is empty here — that's fine,
        # the assistant logic doesn't append empty text).
        user_turns = [t for t in turns if t["role"] == "user"]
        assert len(user_turns) == 1
        assert user_turns[0]["text"] == "hello"

    async def test_multiple_text_frames_one_turn(self) -> None:
        """Streamed assistant response: 3 distinct LLMTextFrames within
        one ``BotStoppedSpeakingFrame`` boundary stitch into ONE turn.
        Each frame is still counted exactly once (dedup acts per-frame,
        not per-turn).
        """
        recorder = TranscriptRecorder()
        conv_state = _FakeProcessor("conv_state")

        for chunk in ("Hello, ", "this is ", "the assistant."):
            frame = LLMTextFrame(text=chunk)
            await recorder.on_frame(frame, conv_state, None, _FakeDirection.DOWNSTREAM)

        await recorder.on_frame(
            BotStoppedSpeakingFrame(),
            conv_state,
            None,
            _FakeDirection.DOWNSTREAM,
        )

        turns = recorder.drain()
        assert len(turns) == 1
        assert turns[0]["text"] == "Hello, this is the assistant."
