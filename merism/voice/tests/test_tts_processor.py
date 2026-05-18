"""Tests for :class:`~merism.voice.processors.tts.TTSProcessor`."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from merism.voice import (
    EndFrame,
    ErrorFrame,
    Frame,
    FrameDirection,
    FrameProcessor,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    Pipeline,
    PipelineTask,
    TTSStoppedFrame,
)
from merism.voice.observer import Observer
from merism.voice.processors.tts import TTSProcessor


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


class FailingTTSClient:
    async def stream_tts(self, _text_iter: AsyncIterator[str]) -> AsyncIterator[bytes]:
        async for _ in _text_iter:
            pass
        if False:
            yield b""
        raise RuntimeError("tts backend unavailable")


@pytest.mark.asyncio
async def test_tts_processor_warms_up_before_first_turn() -> None:
    class WarmupTTSClient:
        def __init__(self) -> None:
            self.warmup_calls = 0

        async def warmup(self, timeout_s: float = 3.0) -> None:
            _ = timeout_s
            self.warmup_calls += 1

        async def stream_tts(self, text_iter: AsyncIterator[str]) -> AsyncIterator[bytes]:
            async for _ in text_iter:
                pass
            if False:
                yield b""

    client = WarmupTTSClient()
    processor = TTSProcessor(client=client)
    task = PipelineTask(Pipeline([processor]))

    await task.start()
    await asyncio.sleep(0.05)
    await task.queue_frame(EndFrame())
    await asyncio.sleep(0.05)
    await task.stop()

    assert client.warmup_calls == 1


@pytest.mark.asyncio
async def test_tts_errors_are_reported_instead_of_silenced() -> None:
    processor = TTSProcessor(client=FailingTTSClient())
    recorder = RecordingObserver()
    task = PipelineTask(Pipeline([processor]), observer=recorder)

    await task.start()
    await task.queue_frame(LLMFullResponseStartFrame(response_id="resp_1"))
    await task.queue_frame(LLMTextFrame(text="你好", response_id="resp_1"))
    await task.queue_frame(LLMFullResponseEndFrame(response_id="resp_1"))
    await asyncio.sleep(0.1)
    await task.queue_frame(EndFrame())
    await asyncio.sleep(0.05)
    await task.stop()

    assert any(isinstance(frame, ErrorFrame) for frame in recorder.seen)
    error = next(frame for frame in recorder.seen if isinstance(frame, ErrorFrame))
    assert error.code == "tts_session_failed"
    assert any(isinstance(frame, TTSStoppedFrame) for frame in recorder.seen)
