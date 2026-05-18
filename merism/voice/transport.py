"""WebSocket transport adapters for pipecat + Django Channels."""

from __future__ import annotations

import asyncio
import logging

from pipecat.frames.frames import AudioRawFrame, Frame, TTSAudioRawFrame, StartFrame, EndFrame, CancelFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

logger = logging.getLogger(__name__)


class WebSocketInputTransport(FrameProcessor):
    """Receives audio via a queue (fed by Django Channels consumer)."""

    def __init__(self, consumer, *, sample_rate: int = 16000, **kwargs):
        super().__init__(name="WSInput", **kwargs)
        self._consumer = consumer
        self._sample_rate = sample_rate
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._task: asyncio.Task | None = None

    def push_audio(self, data: bytes):
        """Called by the consumer's receive() to feed audio."""
        self._queue.put_nowait(data)

    async def start(self, frame: StartFrame):
        await super().start(frame)
        self._task = asyncio.create_task(self._pump())

    async def stop(self, frame: EndFrame):
        if self._task:
            self._task.cancel()
        await super().stop(frame)

    async def cancel(self, frame: CancelFrame):
        if self._task:
            self._task.cancel()
        await super().cancel(frame)

    async def _pump(self):
        try:
            while True:
                data = await self._queue.get()
                await self.push_frame(AudioRawFrame(
                    audio=data,
                    sample_rate=self._sample_rate,
                    num_channels=1,
                ))
        except asyncio.CancelledError:
            pass


class WebSocketOutputTransport(FrameProcessor):
    """Sends TTS audio back to client via Django Channels consumer."""

    def __init__(self, consumer, **kwargs):
        super().__init__(name="WSOutput", **kwargs)
        self._consumer = consumer

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TTSAudioRawFrame):
            try:
                await self._consumer.send(bytes_data=frame.audio)
            except Exception:
                pass
        else:
            await self.push_frame(frame, direction)


class WebSocketTransport:
    """Convenience wrapper."""

    def __init__(self, consumer, *, sample_rate: int = 16000):
        self._consumer = consumer
        self._sample_rate = sample_rate
        self._input = WebSocketInputTransport(consumer, sample_rate=sample_rate)

    def input(self) -> WebSocketInputTransport:
        return self._input

    def output(self) -> WebSocketOutputTransport:
        return WebSocketOutputTransport(self._consumer)
