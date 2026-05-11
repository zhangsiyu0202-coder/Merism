"""Observers — side channels for metrics, recording, logging.

Observers are NOT in the main pipeline. Every frame push fires
``Observer.on_frame`` asynchronously; the observer does whatever it
wants without slowing the pipeline or mutating frames.

Ships three concrete observers:
- :class:`MetricsObserver` — TTFB + per-turn latency.
- :class:`StructlogObserver` — structured log on every frame.
- :class:`TranscriptRecorder` — collects final transcripts + LLM
  output into a list so a consumer can save it to the DB at turn end.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from .frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    Frame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)

if TYPE_CHECKING:
    from .pipeline import FrameDirection, FrameProcessor

logger = logging.getLogger(__name__)


class Observer:
    """Base class — override :meth:`on_frame`.

    ``src`` is the processor pushing the frame; ``dst`` is the next
    hop (``None`` means end-of-pipe in that direction).
    """

    async def on_frame(
        self,
        frame: Frame,
        src: "FrameProcessor",
        dst: "FrameProcessor | None",
        direction: "FrameDirection",
    ) -> None:  # pragma: no cover — base does nothing
        pass


class MetricsObserver(Observer):
    """Emits per-turn latency metrics.

    Tracks four canonical voice-AI metrics:
    - ``stt_latency``:   user_stopped_speaking → transcription_received
    - ``llm_latency``:   llm_response_start → first LLMTextFrame
    - ``tts_ttfb``:      llm_response_end → first TTSAudioRawFrame
    - ``turn_latency``:  user_stopped_speaking → bot_stopped_speaking

    All values reported in milliseconds.
    """

    def __init__(self) -> None:
        self._t_user_stop: float | None = None
        self._t_llm_start: float | None = None
        self._t_llm_end: float | None = None
        self._turn_samples: dict[str, list[float]] = {}

    @property
    def samples(self) -> dict[str, list[float]]:
        return self._turn_samples

    async def on_frame(
        self,
        frame: Frame,
        src: "FrameProcessor",
        dst: "FrameProcessor | None",
        direction: "FrameDirection",
    ) -> None:
        now = time.monotonic()

        if isinstance(frame, UserStartedSpeakingFrame):
            # Reset the per-turn clock tree.
            self._t_user_stop = None
            self._t_llm_start = None
            self._t_llm_end = None
            return

        if isinstance(frame, UserStoppedSpeakingFrame):
            self._t_user_stop = now
            return

        if isinstance(frame, TranscriptionFrame) and self._t_user_stop is not None:
            self._record("stt_latency", (now - self._t_user_stop) * 1000)
            return

        if isinstance(frame, LLMFullResponseStartFrame):
            self._t_llm_start = now
            return

        if isinstance(frame, LLMTextFrame) and self._t_llm_start is not None:
            self._record("llm_latency", (now - self._t_llm_start) * 1000)
            # Only record first-token latency — clear the mark.
            self._t_llm_start = None
            return

        if isinstance(frame, LLMFullResponseEndFrame):
            self._t_llm_end = now
            return

        if isinstance(frame, TTSAudioRawFrame) and self._t_llm_end is not None:
            self._record("tts_ttfb", (now - self._t_llm_end) * 1000)
            self._t_llm_end = None
            return

        if isinstance(frame, BotStoppedSpeakingFrame) and self._t_user_stop is not None:
            self._record("turn_latency", (now - self._t_user_stop) * 1000)
            self._t_user_stop = None
            return

    def _record(self, kind: str, ms: float) -> None:
        self._turn_samples.setdefault(kind, []).append(ms)
        logger.info("voice.metrics", extra={"kind": kind, "ms": round(ms, 1)})

    def summary(self) -> dict[str, dict[str, float]]:
        """Return p50 / p90 / mean for each metric kind."""
        out: dict[str, dict[str, float]] = {}
        for kind, samples in self._turn_samples.items():
            if not samples:
                continue
            srt = sorted(samples)
            n = len(srt)
            out[kind] = {
                "count": float(n),
                "mean": sum(srt) / n,
                "p50": srt[n // 2],
                "p90": srt[int(n * 0.9)] if n > 1 else srt[0],
                "max": srt[-1],
            }
        return out


class StructlogObserver(Observer):
    """Log every frame push at DEBUG level, useful for trace bringup."""

    async def on_frame(
        self,
        frame: Frame,
        src: "FrameProcessor",
        dst: "FrameProcessor | None",
        direction: "FrameDirection",
    ) -> None:
        logger.debug(
            "voice.frame",
            extra={
                "name": frame.name,
                "src": src.name,
                "dst": dst.name if dst else None,
                "dir": direction.value,
            },
        )


class TranscriptRecorder(Observer):
    """Collects the conversation transcript for end-of-turn persistence.

    Pairs well with ``InterviewSession.transcript`` — at EndFrame, call
    :meth:`drain` and save the returned list to the session row.
    """

    def __init__(self) -> None:
        self._turns: list[dict[str, str]] = []
        self._pending_user = ""
        self._pending_bot: list[str] = []

    async def on_frame(
        self,
        frame: Frame,
        src: "FrameProcessor",
        dst: "FrameProcessor | None",
        direction: "FrameDirection",
    ) -> None:
        if isinstance(frame, TranscriptionFrame):
            self._pending_user = frame.text
            return
        if isinstance(frame, LLMTextFrame):
            self._pending_bot.append(frame.text)
            return
        if isinstance(frame, BotStoppedSpeakingFrame):
            if self._pending_user:
                self._turns.append({"role": "user", "text": self._pending_user})
                self._pending_user = ""
            if self._pending_bot:
                self._turns.append({"role": "assistant", "text": "".join(self._pending_bot)})
                self._pending_bot = []

    def drain(self) -> list[dict[str, str]]:
        """Return + clear buffered turns."""
        turns = list(self._turns)
        self._turns.clear()
        return turns


class CompositeObserver(Observer):
    """Fan out frames to multiple observers."""

    def __init__(self, *observers: Observer) -> None:
        self._observers = observers

    async def on_frame(
        self,
        frame: Frame,
        src: "FrameProcessor",
        dst: "FrameProcessor | None",
        direction: "FrameDirection",
    ) -> None:
        for obs in self._observers:
            await obs.on_frame(frame, src, dst, direction)
