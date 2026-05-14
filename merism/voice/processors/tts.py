"""TTS FrameProcessor — turns :class:`LLMTextFrame` stream into audio.

Lifecycle per turn:
- :class:`LLMFullResponseStartFrame` → open CosyVoice session, remember
  the incoming ``response_id``.
- :class:`LLMTextFrame` → append to text buffer, forward as
  :class:`TTSTextFrame` so recorders see it.
- TTS yields audio → push :class:`TTSAudioRawFrame` tagged with
  ``response_id``; increment an internal byte counter.
- :class:`LLMFullResponseEndFrame` → close the text stream, let TTS
  drain, emit :class:`BotStoppedSpeakingFrame`.

OpenAI-Realtime-inspired truncation: on :class:`InterruptionFrame` we
(a) cancel the in-flight TTS session, (b) compute how many ms of audio
we'd produced so far, (c) push a :class:`TruncatedFrame` downstream so
:class:`ConversationState` can trim history to what the user HEARD.
"""

from __future__ import annotations

import asyncio
import logging

from merism.tts import CosyVoiceClient
from merism.voice.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    CancelFrame,
    EndFrame,
    Frame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    StartFrame,
    TruncatedFrame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    TTSTextFrame,
)
from merism.voice.pipeline import FrameDirection, FrameProcessor

logger = logging.getLogger(__name__)


class TTSProcessor(FrameProcessor):
    """Streaming TTS — feeds LLM tokens into realtime TTS.

    Provider-agnostic: accepts any client that implements ``stream_tts(text_iter)``.
    Defaults to CosyVoiceClient for backward compatibility.
    """

    BYTES_PER_SAMPLE = 2   # PCM16 mono

    def __init__(
        self,
        *,
        client: CosyVoiceClient | None = None,
        voice: str = "Cherry",
        language_type: str = "Chinese",
        sample_rate: int = 24000,
        name: str = "TTS",
    ) -> None:
        super().__init__(name)
        self._client = client or CosyVoiceClient(voice=voice, language_type=language_type)
        self._sample_rate = sample_rate
        self._text_in: asyncio.Queue[str] | None = None
        self._tts_task: asyncio.Task[None] | None = None
        self._bot_speaking = False
        # Per-response state
        self._current_response_id: str = ""
        self._bytes_emitted: int = 0

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        if isinstance(frame, StartFrame):
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, (EndFrame, CancelFrame)):
            await self._abort_session()
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, InterruptionFrame):
            # Compute the truncation point BEFORE tearing things down.
            played_ms = self._current_played_ms()
            response_id = self._current_response_id
            await self._abort_session()
            if self._bot_speaking:
                self._bot_speaking = False
                await self.push_frame(BotStoppedSpeakingFrame(response_id=response_id))
            # Announce the truncation point so ConversationState can trim.
            # Prefer the caller's played_ms if they tracked it (frontend
            # knows from AudioPlayback scheduling), else fall back to
            # our byte-count estimate.
            final_ms = frame.audio_played_ms or played_ms
            final_id = frame.response_id or response_id
            if final_id:
                await self.push_frame(
                    TruncatedFrame(
                        response_id=final_id,
                        audio_played_ms=final_ms,
                    )
                )
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, LLMFullResponseStartFrame):
            self._current_response_id = frame.response_id
            self._bytes_emitted = 0
            self._text_in = asyncio.Queue()
            self._tts_task = asyncio.create_task(
                self._run_session(self._text_in, frame.response_id)
            )
            await self.push_frame(TTSStartedFrame(response_id=frame.response_id), direction)
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, LLMTextFrame) and self._text_in is not None:
            await self._text_in.put(frame.text)
            await self.push_frame(
                TTSTextFrame(text=frame.text, response_id=frame.response_id), direction
            )
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, LLMFullResponseEndFrame):
            if self._text_in is not None:
                await self._text_in.put("")   # sentinel — drains the pump
            await self.push_frame(frame, direction)
            return

        await self.push_frame(frame, direction)

    def _current_played_ms(self) -> int:
        """Estimate ms of audio we've emitted for the current response.

        Note: this is the SERVER-SIDE estimate — ms produced, not ms
        heard. Frontend should pass the real heard-ms via
        :data:`InterruptionFrame.audio_played_ms` when it can; this is
        the fallback.
        """
        if self._sample_rate <= 0:
            return 0
        samples = self._bytes_emitted // self.BYTES_PER_SAMPLE
        return int(samples * 1000 / self._sample_rate)

    async def _run_session(
        self, text_in: asyncio.Queue[str], response_id: str
    ) -> None:
        async def text_iter():
            while True:
                chunk = await text_in.get()
                if not chunk:
                    break
                yield chunk

        try:
            async for audio in self._client.stream_tts(text_iter()):
                if not audio:
                    continue
                self._bytes_emitted += len(audio)
                if not self._bot_speaking:
                    self._bot_speaking = True
                    await self.push_frame(BotStartedSpeakingFrame(response_id=response_id))
                await self.push_frame(
                    TTSAudioRawFrame(
                        audio=audio,
                        sample_rate=self._sample_rate,
                        response_id=response_id,
                    )
                )
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning("voice.tts.session_failed", extra={"error": str(exc)})
        finally:
            if self._bot_speaking:
                self._bot_speaking = False
                await self.push_frame(BotStoppedSpeakingFrame(response_id=response_id))
            await self.push_frame(TTSStoppedFrame(response_id=response_id))

    async def _abort_session(self) -> None:
        if self._text_in is not None:
            try:
                self._text_in.put_nowait("")
            except asyncio.QueueFull:
                pass
        if self._tts_task is not None:
            self._tts_task.cancel()
            try:
                await self._tts_task
            except (asyncio.CancelledError, Exception):
                pass
            self._tts_task = None
        self._text_in = None
