"""Tests for :class:`~merism.voice.processors.stt.STTProcessor`."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from merism.voice import EndFrame, Pipeline, PipelineTask
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
