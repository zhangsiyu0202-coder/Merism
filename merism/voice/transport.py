"""WebSocket transport for pipecat — bridges Django Channels WebSocket.

Pipecat's built-in WebSocket transport expects a standalone server.
We need an adapter that works with Django Channels' WebSocket consumer.
"""

from __future__ import annotations

import asyncio
import logging

from pipecat.frames.frames import AudioRawFrame, Frame, TTSAudioRawFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

logger = logging.getLogger(__name__)


class WebSocketInputTransport(FrameProcessor):
    """Reads audio from Django Channels WebSocket, emits AudioRawFrame."""

    def __init__(self, websocket, *, sample_rate: int = 16000, **kwargs):
        super().__init__(name="WSInput", **kwargs)
        self._ws = websocket
        self._sample_rate = sample_rate
        self._receive_task: asyncio.Task | None = None

    async def start(self, frame):
        await super().start(frame)
        self._receive_task = asyncio.create_task(self._receive_loop())

    async def stop(self, frame):
        if self._receive_task:
            self._receive_task.cancel()
        await super().stop(frame)

    async def _receive_loop(self):
        try:
            while True:
                data = await self._ws.receive_bytes()
                if data:
                    await self.push_frame(AudioRawFrame(
                        audio=data,
                        sample_rate=self._sample_rate,
                        num_channels=1,
                    ))
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.debug("ws_input.closed", extra={"reason": str(exc)})


class WebSocketOutputTransport(FrameProcessor):
    """Sends TTSAudioRawFrame back to client via WebSocket."""

    def __init__(self, websocket, **kwargs):
        super().__init__(name="WSOutput", **kwargs)
        self._ws = websocket

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TTSAudioRawFrame):
            try:
                await self._ws.send_bytes(frame.audio)
            except Exception:
                pass
        else:
            await self.push_frame(frame, direction)


class WebSocketTransport:
    """Convenience wrapper providing input() and output() processors."""

    def __init__(self, websocket, *, sample_rate: int = 16000):
        self._ws = websocket
        self._sample_rate = sample_rate

    def input(self) -> WebSocketInputTransport:
        return WebSocketInputTransport(self._ws, sample_rate=self._sample_rate)

    def output(self) -> WebSocketOutputTransport:
        return WebSocketOutputTransport(self._ws)
