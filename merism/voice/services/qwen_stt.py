"""Qwen Paraformer STT service for pipecat."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    Frame,
    InterimTranscriptionFrame,
    StartFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.frames.frames import AudioRawFrame

from merism.stt import ParaformerClient, should_ignore_transcript

logger = logging.getLogger(__name__)


class QwenSTTService(FrameProcessor):
    """Pipecat-compatible STT using Qwen Paraformer realtime.

    Receives AudioRawFrame, streams to Paraformer, emits
    TranscriptionFrame when a final transcript is ready.
    """

    def __init__(self, *, sample_rate: int = 16000, language: str = "zh", **kwargs):
        super().__init__(name="QwenSTT", **kwargs)
        self._sample_rate = sample_rate
        self._language = language
        self._client: ParaformerClient | None = None
        self._task: asyncio.Task | None = None
        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def start(self, frame: StartFrame):
        await super().start(frame)
        self._client = ParaformerClient(
            sample_rate=self._sample_rate,
            language=self._language,
            use_server_vad=False,
        )
        self._task = asyncio.create_task(self._recognition_loop())

    async def stop(self, frame: EndFrame):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._client:
            await self._client.close()
        await super().stop(frame)

    async def cancel(self, frame: CancelFrame):
        if self._task:
            self._task.cancel()
        await super().cancel(frame)

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, AudioRawFrame):
            await self._audio_queue.put(frame.audio)
        elif isinstance(frame, (StartFrame, EndFrame, CancelFrame)):
            # Handled by lifecycle methods
            pass
        else:
            await self.push_frame(frame, direction)

    async def _recognition_loop(self):
        """Stream audio to Paraformer and emit transcriptions."""
        try:
            async for result in self._client.stream(self._audio_iter()):
                if result.is_final:
                    text = result.text.strip()
                    if text and not should_ignore_transcript(text):
                        await self.push_frame(TranscriptionFrame(
                            text=text,
                            user_id="participant",
                            timestamp=str(result.timestamp_ms),
                        ))
                else:
                    text = result.text.strip()
                    if text and not should_ignore_transcript(text):
                        await self.push_frame(InterimTranscriptionFrame(
                            text=text,
                            user_id="participant",
                            timestamp=str(result.timestamp_ms),
                        ))
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning("qwen_stt.recognition_failed", extra={"error": str(exc)})

    async def _audio_iter(self) -> AsyncGenerator[bytes, None]:
        while True:
            chunk = await self._audio_queue.get()
            yield chunk
