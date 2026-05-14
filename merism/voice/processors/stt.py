"""STT FrameProcessor wrapping :class:`merism.stt.ParaformerClient`.

Receives :class:`~merism.voice.frames.InputAudioRawFrame` from upstream,
buffers them into an async iterator, feeds to Paraformer, emits:

- :class:`InterimTranscriptionFrame` on partials
- :class:`TranscriptionFrame` on final
- :class:`UserStartedSpeakingFrame` + :class:`UserStoppedSpeakingFrame`
  on VAD boundaries (these are ``SystemFrame`` so they bypass the
  regular queue and survive interruption)

The Paraformer WS is opened lazily on first audio and held open for
the life of the processor.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from merism.stt import ParaformerClient, STTEvent
from merism.voice.frames import (
    CancelFrame,
    EndFrame,
    Frame,
    InputAudioRawFrame,
    InterimTranscriptionFrame,
    InterruptionFrame,
    StartFrame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from merism.voice.pipeline import FrameDirection, FrameProcessor

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class STTProcessor(FrameProcessor):
    """DashScope Qwen-ASR as a pipeline processor.

    Provider-agnostic: accepts any client that implements ``stream_stt(audio_iter)``.
    Defaults to ParaformerClient for backward compatibility.
    """

    def __init__(
        self,
        *,
        client: ParaformerClient | None = None,
        language: str = "zh",
        name: str = "STT",
    ) -> None:
        super().__init__(name)
        self._client = client or ParaformerClient(language=language)
        self._audio_in: asyncio.Queue[bytes] | None = None
        self._stream_task: asyncio.Task[None] | None = None
        self._user_speaking = False

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        if isinstance(frame, StartFrame):
            self._audio_in = asyncio.Queue()
            self._stream_task = asyncio.create_task(self._run_stream())
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, (EndFrame, CancelFrame)):
            await self._shutdown()
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, InterruptionFrame):
            # Flush any queued audio so we don't process stale speech
            # after the user barged in.
            if self._audio_in is not None:
                while not self._audio_in.empty():
                    try:
                        self._audio_in.get_nowait()
                    except asyncio.QueueEmpty:
                        break
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, InputAudioRawFrame):
            if self._audio_in is not None:
                await self._audio_in.put(frame.audio)
            # Forward the frame too — observers (RecordingObserver,
            # metrics) and any future middleware downstream need to see
            # the audio. STT is a fan-out, not a consumer.
            await self.push_frame(frame, direction)
            return

        # pass-through for all other types
        await self.push_frame(frame, direction)

    async def _run_stream(self) -> None:
        assert self._audio_in is not None

        async def audio_iter():
            while True:
                chunk = await self._audio_in.get()
                if not chunk:
                    break
                yield chunk

        try:
            async for event in self._client.stream_stt(audio_iter()):
                await self._handle_event(event)
        except Exception as exc:
            logger.warning("voice.stt.stream_error", extra={"error": str(exc)})

    async def _handle_event(self, event: STTEvent) -> None:
        if not event.text:
            return
        # Emit speaking-start on first interim of a turn.
        if not self._user_speaking:
            self._user_speaking = True
            await self.push_frame(UserStartedSpeakingFrame())

        if event.is_final:
            self._user_speaking = False
            await self.push_frame(UserStoppedSpeakingFrame())
            await self.push_frame(
                TranscriptionFrame(text=event.text, confidence=event.confidence)
            )
        else:
            await self.push_frame(InterimTranscriptionFrame(text=event.text))

    async def _shutdown(self) -> None:
        if self._audio_in is not None:
            # Sentinel drains the generator.
            await self._audio_in.put(b"")
        if self._stream_task is not None:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except (asyncio.CancelledError, Exception):
                pass
