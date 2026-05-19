"""Frame taxonomy — the unit of data moving through the voice pipeline.

Design directly inspired by :mod:`pipecat` (BSD-2). Three base classes
govern queueing priority + interruption semantics:

- :class:`SystemFrame` — high priority, survives interruption. Used for
  control signals that must not be dropped: ``InterruptionFrame``,
  ``ErrorFrame``, ``UserStartedSpeakingFrame``.
- :class:`DataFrame` — audio / text / etc. Dropped on interruption.
- :class:`ControlFrame` — boundaries (turn start / end, response
  start / end). Ordered, not dropped.

Every processor inspects ``type(frame)`` to decide what to do. Frames
auto-number via ``_FRAME_SEQ`` for log correlation.
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass, field
from typing import Any

_FRAME_SEQ = itertools.count(1)


def _next_id() -> int:
    return next(_FRAME_SEQ)


# ── base classes ────────────────────────────────────────────


@dataclass
class Frame:
    """Root type. All data in the pipeline flows as subclasses."""

    id: int = field(default_factory=_next_id, init=False)
    ts: float = field(default_factory=time.monotonic, init=False)

    @property
    def name(self) -> str:
        """Short debug label — ``TranscriptionFrame#42``."""
        return f"{type(self).__name__}#{self.id}"


@dataclass
class SystemFrame(Frame):
    """High-priority, not discarded on interruption."""


@dataclass
class DataFrame(Frame):
    """Queued + ordered. Dropped when upstream emits InterruptionFrame."""


@dataclass
class ControlFrame(Frame):
    """Ordered boundary signals (turn/response start/end)."""


# ── lifecycle / system ─────────────────────────────────────


@dataclass
class StartFrame(SystemFrame):
    """Pipeline warm-up. Processors may allocate here."""

    sample_rate: int = 16000


@dataclass
class EndFrame(ControlFrame):
    """Graceful shutdown — drain queues, flush, clean up."""


@dataclass
class CancelFrame(SystemFrame):
    """Hard cancel — abandon in-flight work immediately."""


@dataclass
class ErrorFrame(SystemFrame):
    code: str = ""
    message: str = ""
    fatal: bool = False


# ── turn + interruption ───────────────────────────────────


@dataclass
class UserStartedSpeakingFrame(SystemFrame):
    """PTT start / speech start detected by the client or server."""


@dataclass
class UserStoppedSpeakingFrame(SystemFrame):
    """PTT end / speech end detected by the client or server."""


@dataclass
class BotStartedSpeakingFrame(ControlFrame):
    """TTS began emitting audio for this turn."""

    response_id: str = ""


@dataclass
class BotStoppedSpeakingFrame(ControlFrame):
    """TTS drained audio for this turn."""

    response_id: str = ""


@dataclass
class InterruptionFrame(SystemFrame):
    """Barge-in — every downstream processor should drop buffered work.

    ``audio_played_ms`` is the caller's best estimate of how much of the
    bot's audio reached the user before interruption (0 if unknown).
    ``response_id`` identifies the bot response that was interrupted.
    Together these feed :class:`TruncatedFrame` so the conversation
    history reflects what was HEARD, not what was GENERATED.
    """

    response_id: str = ""
    audio_played_ms: int = 0


# ── data ───────────────────────────────────────────────────


@dataclass
class InputAudioRawFrame(DataFrame):
    """PCM16 mono bytes from the microphone."""

    audio: bytes = b""
    sample_rate: int = 16000


@dataclass
class OutputAudioRawFrame(DataFrame):
    """PCM bytes destined for the speaker."""

    audio: bytes = b""
    sample_rate: int = 24000


@dataclass
class TranscriptionFrame(DataFrame):
    """Final transcript of the user's turn."""

    text: str = ""
    confidence: float = 1.0


@dataclass
class InterimTranscriptionFrame(DataFrame):
    """Partial transcript — may be overwritten by a later interim/final."""

    text: str = ""


@dataclass
class LLMTextFrame(DataFrame):
    """Token / chunk from the LLM."""

    text: str = ""
    response_id: str = ""


@dataclass
class TTSTextFrame(DataFrame):
    """Text fed INTO the TTS (for transcript capture)."""

    text: str = ""
    response_id: str = ""


@dataclass
class TTSAudioRawFrame(DataFrame):
    """Audio OUTPUT from TTS — same as OutputAudioRawFrame, different provenance."""

    audio: bytes = b""
    sample_rate: int = 24000
    response_id: str = ""


# ── control / boundaries ──────────────────────────────────


@dataclass
class LLMFullResponseStartFrame(ControlFrame):
    """LLM started emitting a response."""

    response_id: str = ""


@dataclass
class LLMFullResponseEndFrame(ControlFrame):
    """LLM finished this response."""

    response_id: str = ""


@dataclass
class TTSStartedFrame(ControlFrame):
    """TTS started audio output."""

    response_id: str = ""


@dataclass
class TTSStoppedFrame(ControlFrame):
    """TTS finished audio output for this request."""

    response_id: str = ""


# ── truncation (OpenAI-Realtime-inspired) ──────────────────


@dataclass
class TruncatedFrame(SystemFrame):
    """Emitted right after ``InterruptionFrame``.

    Carries the response_id that was interrupted + how many milliseconds
    of its audio actually reached the user's ear. Downstream
    ``ConversationState`` uses this to truncate the stored transcript so
    the LLM's future context reflects what was HEARD, not what was
    GENERATED. Without this, barge-in breaks multi-turn coherence.

    Modelled after OpenAI's ``conversation.item.truncate`` event.
    """

    response_id: str = ""
    audio_played_ms: int = 0


# ── function calling (OpenAI-inspired — future wiring) ─────


@dataclass
class FunctionCallFrame(DataFrame):
    """LLM requested a tool call mid-response. call_id correlates with the result."""

    call_id: str = ""
    name: str = ""
    arguments: str = ""          # raw JSON string, parsed by the executor


@dataclass
class FunctionCallResultFrame(DataFrame):
    """Result to feed back to the LLM for the given call_id."""

    call_id: str = ""
    result: str = ""


# ── metrics ───────────────────────────────────────────────


@dataclass
class MetricsFrame(SystemFrame):
    """Emitted by MetricsObserver, not a processor."""

    kind: str = ""                        # e.g. "ttfb", "stt_latency"
    value: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


# ── concept testing ────────────────────────────────────────


@dataclass
class StimulusShowFrame(DataFrame):
    """Concept-rotation boundary — ask the client to overlay a stimulus.

    Emitted by the conductor when the current question's concept
    context differs from the previous one. The
    :class:`WebSocketEgressObserver` translates this to the
    :class:`StimulusShowMessage` wire message.
    """

    stimulus_id: str = ""
    kind: str = "image"                   # image / video / text / pdf / link
    content: dict[str, Any] = field(default_factory=dict)
    concept_index: int | None = None
    concept_count: int | None = None
    block_title: str | None = None
