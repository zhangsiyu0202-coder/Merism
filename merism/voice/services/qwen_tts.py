"""Qwen CosyVoice TTS service for pipecat."""

from __future__ import annotations

import asyncio
import logging

from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    Frame,
    StartFrame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    TextFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from merism.tts import CosyVoiceClient

logger = logging.getLogger(__name__)


class QwenTTSService(FrameProcessor):
    """Pipecat-compatible TTS using Qwen CosyVoice streaming.

    Receives TextFrame, streams to CosyVoice, emits TTSAudioRawFrame.
    Buffers text until a complete sentence before sending to TTS.
    """

    def __init__(
        self,
        *,
        voice: str = "Cherry",
        language_type: str = "Chinese",
        sample_rate: int = 24000,
        **kwargs,
    ):
        super().__init__(name="QwenTTS", **kwargs)
        self._voice = voice
        self._language_type = language_type
        self._sample_rate = sample_rate
        self._client: CosyVoiceClient | None = None
        self._text_buffer: list[str] = []
        self._speaking = False

    async def start(self, frame: StartFrame):
        await super().start(frame)
        self._client = CosyVoiceClient(
            voice=self._voice,
            language_type=self._language_type,
        )
        warmup = getattr(self._client, "warmup", None)
        if callable(warmup):
            try:
                await warmup()
            except Exception as exc:
                logger.warning("qwen_tts.warmup_failed", extra={"error": str(exc)})

    async def stop(self, frame: EndFrame):
        await self._flush()
        await super().stop(frame)

    async def cancel(self, frame: CancelFrame):
        self._text_buffer.clear()
        await super().cancel(frame)

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TextFrame):
            self._text_buffer.append(frame.text)
            # Flush on sentence boundaries
            combined = "".join(self._text_buffer)
            if any(combined.endswith(p) for p in ("。", "！", "？", ".", "!", "?", "\n")):
                await self._flush()
        elif isinstance(frame, (StartFrame, EndFrame, CancelFrame)):
            pass
        else:
            await self.push_frame(frame, direction)

    async def _flush(self):
        """Send buffered text to TTS and emit audio frames."""
        text = "".join(self._text_buffer).strip()
        self._text_buffer.clear()

        if not text or not self._client:
            return

        await self.push_frame(TTSStartedFrame())

        try:
            async def text_iter():
                yield text

            async for audio_chunk in self._client.stream_tts(text_iter()):
                if audio_chunk:
                    await self.push_frame(TTSAudioRawFrame(
                        audio=audio_chunk,
                        sample_rate=self._sample_rate,
                        num_channels=1,
                    ))
        except Exception as exc:
            logger.warning("qwen_tts.stream_failed", extra={"error": str(exc)})

        await self.push_frame(TTSStoppedFrame())
