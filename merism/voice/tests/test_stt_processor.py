"""Tests for :class:`~merism.voice.processors.stt.STTProcessor`."""
# ruff: noqa: RUF001

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from merism.stt import STTEvent
from merism.voice import (
    EndFrame,
    Frame,
    FrameDirection,
    FrameProcessor,
    InputAudioRawFrame,
    Pipeline,
    PipelineTask,
    TranscriptionFrame,
    UserStoppedSpeakingFrame,
)
from merism.voice.observer import Observer
from merism.voice.processors.stt import STTProcessor


class WarmupSTTClient:
    def __init__(self) -> None:
        self.warmup_calls = 0

    async def warmup(self, timeout_s: float = 3.0) -> None:
        _ = timeout_s
        self.warmup_calls += 1

    async def stream_stt(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        async for _ in audio_stream:
            pass
        if False:
            yield b""


class RecordingObserver(Observer):
    def __init__(self) -> None:
        self.seen: list[Frame] = []

    async def on_frame(
        self,
        frame: Frame,
        src: FrameProcessor,
        dst: FrameProcessor | None,
        direction: FrameDirection,
    ) -> None:
        self.seen.append(frame)


class ManualCommitSTTClient:
    async def warmup(self, timeout_s: float = 3.0) -> None:
        _ = timeout_s

    async def stream_stt(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[STTEvent]:
        saw_audio = False
        async for chunk in audio_stream:
            if chunk:
                saw_audio = True
                yield STTEvent(text="你好", is_final=False, confidence=0.99)
        if saw_audio:
            yield STTEvent(text="你好，我想了解一下", is_final=True, confidence=0.99)


class SilentSTTClient:
    async def warmup(self, timeout_s: float = 3.0) -> None:
        _ = timeout_s

    async def stream_stt(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[STTEvent]:
        async for _ in audio_stream:
            pass
        if False:
            yield STTEvent(text="", is_final=True, confidence=0.0)


@pytest.mark.asyncio
async def test_stt_processor_warms_up_before_first_turn() -> None:
    client = WarmupSTTClient()
    processor = STTProcessor(client=client)
    task = PipelineTask(Pipeline([processor]))

    await task.start()
    await asyncio.sleep(0.05)
    await task.queue_frame(EndFrame())
    await asyncio.sleep(0.05)
    await task.stop()

    assert client.warmup_calls == 1


@pytest.mark.asyncio
async def test_stt_processor_commits_turn_on_explicit_stop() -> None:
    processor = STTProcessor(client=ManualCommitSTTClient())
    recorder = RecordingObserver()
    task = PipelineTask(Pipeline([processor]), observer=recorder)

    await task.start()
    await task.queue_frame(InputAudioRawFrame(audio=b"\x00" * 3200))
    # Yield to the event loop so the STT stream task picks up the audio
    # chunk BEFORE _close_turn fires. Without this, queue.put + immediate
    # close drain the stream before the first STTEvent is yielded.
    await asyncio.sleep(0.05)
    await task.queue_frame(UserStoppedSpeakingFrame())
    await asyncio.sleep(0.2)
    await task.queue_frame(EndFrame())
    await asyncio.sleep(0.05)
    await task.stop()

    transcripts = [frame for frame in recorder.seen if isinstance(frame, TranscriptionFrame)]
    assert any(frame.text == "你好，我想了解一下" for frame in transcripts)


@pytest.mark.asyncio
async def test_stt_processor_does_not_emit_transcript_for_empty_turn() -> None:
    processor = STTProcessor(client=SilentSTTClient())
    recorder = RecordingObserver()
    task = PipelineTask(Pipeline([processor]), observer=recorder)

    await task.start()
    await task.queue_frame(UserStoppedSpeakingFrame())
    await asyncio.sleep(0.1)
    await task.queue_frame(EndFrame())
    await asyncio.sleep(0.05)
    await task.stop()

    transcripts = [frame for frame in recorder.seen if isinstance(frame, TranscriptionFrame)]
    assert transcripts == []
