"""STT FrameProcessor wrapping :class:`merism.stt.ParaformerClient`.

Receives :class:`~merism.voice.frames.InputAudioRawFrame` from upstream,
buffers them into an async iterator, feeds to Paraformer, emits:

- :class:`InterimTranscriptionFrame` on partials
- :class:`TranscriptionFrame` on final
- :class:`UserStartedSpeakingFrame` + :class:`UserStoppedSpeakingFrame`
  on PTT boundaries

The Paraformer WS is opened lazily on first audio and held open for
the life of the processor.
"""

from __future__ import annotations

import asyncio
import logging

from merism.stt import ParaformerClient, STTEvent, should_ignore_transcript
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

logger = logging.getLogger(__name__)


class STTProcessor(FrameProcessor):
    """DashScope Qwen-ASR as a pipeline processor."""

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
        self._turn_closing = False

    async def start(self) -> None:
        if self._started:
            return
        warmup = getattr(self._client, "warmup", None)
        if callable(warmup):
            try:
                await warmup()
            except Exception as exc:
                logger.warning("voice.stt.warmup_failed", extra={"error": str(exc)})
        await super().start()

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        if isinstance(frame, StartFrame):
            self._start_stream_if_needed()
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, (EndFrame, CancelFrame)):
            await self._shutdown()
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, UserStartedSpeakingFrame):
            self._start_stream_if_needed()
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, UserStoppedSpeakingFrame):
            await self._close_turn()
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, InterruptionFrame):
            if self._audio_in is not None:
                while not self._audio_in.empty():
                    try:
                        self._audio_in.get_nowait()
                    except asyncio.QueueEmpty:
                        break
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, InputAudioRawFrame):
            if self._turn_closing:
                await self.push_frame(frame, direction)
                return
            self._start_stream_if_needed()
            if self._audio_in is not None:
                await self._audio_in.put(frame.audio)
            await self.push_frame(frame, direction)
            return

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
        finally:
            self._turn_closing = False
            self._audio_in = None
            self._stream_task = None

    def _start_stream_if_needed(self) -> None:
        if self._turn_closing:
            return
        if self._audio_in is None or self._stream_task is None or self._stream_task.done():
            self._audio_in = asyncio.Queue()
            self._stream_task = asyncio.create_task(self._run_stream())

    async def _handle_event(self, event: STTEvent) -> None:
        if not event.text or should_ignore_transcript(event.text):
            if event.text:
                logger.info(
                    "voice.stt.transcript_suppressed",
                    extra={"text": event.text[:32], "is_final": event.is_final},
                )
            return
        if not self._user_speaking:
            self._user_speaking = True
            await self.push_frame(UserStartedSpeakingFrame())

        if event.is_final:
            self._user_speaking = False
            if not self._turn_closing:
                await self.push_frame(UserStoppedSpeakingFrame())
            await self.push_frame(
                TranscriptionFrame(text=event.text, confidence=event.confidence)
            )
        else:
            await self.push_frame(InterimTranscriptionFrame(text=event.text))

    async def _close_turn(self) -> None:
        if self._audio_in is None or self._turn_closing:
            return
        self._turn_closing = True
        await self._audio_in.put(b"")
        task = self._stream_task
        if task is None:
            self._turn_closing = False
            self._audio_in = None
            return
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except asyncio.TimeoutError:
            logger.warning("voice.stt.turn_close_timeout")
        except Exception as exc:
            logger.warning("voice.stt.turn_close_failed", extra={"error": str(exc)})

    async def _shutdown(self) -> None:
        if self._audio_in is not None:
            await self._audio_in.put(b"")
        if self._stream_task is not None:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except (asyncio.CancelledError, Exception):
                pass
        self._turn_closing = False
