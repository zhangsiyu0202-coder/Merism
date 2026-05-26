"""WebSocket voice protocol — Pydantic message types.

Single wire format: JSON text frames for control, binary frames for audio.
Every text message has a ``type`` discriminator so both sides can switch on it.

Why not binary everywhere?
- Debugging voice issues in the field requires a human-readable log.
  JSON control + binary audio is the pattern Deepgram / OpenAI Realtime /
  Vapi all use.
- Keeps the control plane testable without a WebSocket client — you can
  validate messages with ``pydantic`` alone.

Frame dispatch:
- Text frame  → JSON → one of the ``*Message`` classes below.
- Binary frame → server-side raw audio (client→server: PCM16 16kHz mono;
                 server→client: output audio, same encoding).

See :class:`~merism.realtime.voice.VoiceConsumer` for the router.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


# ── Client → Server ────────────────────────────────────────


class SessionStartMessage(BaseModel):
    """First message from client after WS handshake.

    The server resolves the session from the URL path, so this message
    only carries participant-specific preferences. ``client_prefers_barge_in``
    is now a no-op — barge-in is disabled product-wide (2026-05-25,
    superseding ADR 0002). Kept on the wire for protocol stability;
    the server ignores its value.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["session_start"]
    sample_rate: int = 16000  # PCM16 16 kHz mono — Paraformer native
    client_prefers_barge_in: bool = False


class PttSpeakingStartMessage(BaseModel):
    """Client-side push-to-talk speech start.

    ``audio_played_ms`` is the amount of the current bot response the
    user has actually heard, measured from the browser's AudioContext
    clock (see ``AudioPlayback.getPlayedMs()``). Zero when nothing is
    playing. Feeds :class:`~merism.voice.frames.TruncatedFrame` so the
    conversation history reflects what was HEARD.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["ptt_speaking_start"] = "ptt_speaking_start"
    ts: float = Field(..., description="Client-side timestamp (seconds since session start).")
    audio_played_ms: int = Field(
        0,
        ge=0,
        description="Ms of current bot response already played to user (0 if silent).",
    )


class PttSpeakingEndMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["ptt_speaking_end"] = "ptt_speaking_end"
    ts: float


class InterruptionMessage(BaseModel):
    """Explicit user-initiated barge-in (e.g. tapping a "cancel" button).

    Distinct from push-to-talk barge-in because it's deterministic —
    user clicked Cancel, not a threshold. Carries the same
    ``audio_played_ms`` semantics so truncation is precise.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["interrupt"]
    audio_played_ms: int = Field(0, ge=0)


class TextInputMessage(BaseModel):
    """Fallback for participants who can't / won't use voice.

    PRODUCT.md §3.5 — the right-column input is the degraded-mode channel.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["text_input"]
    text: str = Field(..., min_length=1)


class AttachmentUploadedMessage(BaseModel):
    """Participant uploaded an image/video/PDF via the attachment button."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["attachment_uploaded"]
    storage_key: str
    kind: Literal["image", "video", "pdf"]


class PingMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["ping"]


ClientMessage = Annotated[
    Union[
        SessionStartMessage,
        PttSpeakingStartMessage,
        PttSpeakingEndMessage,
        TextInputMessage,
        AttachmentUploadedMessage,
        InterruptionMessage,
        PingMessage,
    ],
    Field(discriminator="type"),
]


# ── Server → Client ────────────────────────────────────────


class SessionReadyMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["session_ready"] = "session_ready"
    session_id: str
    output_sample_rate: int = 24000  # CosyVoice native
    # ``barge_in_enabled`` was previously sent here to let the client
    # gate its PTT button. The field was removed on 2026-05-25 when
    # we standardized on strict push-to-talk: the AI is never
    # interrupted. The frontend hardcodes the equivalent of
    # ``barge_in_enabled=False`` and disables the PTT button while
    # the bot is speaking.


class PartialTranscriptMessage(BaseModel):
    """Interim STT output; updates the participant's live caption bubble."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["partial_transcript"] = "partial_transcript"
    text: str


class FinalTranscriptMessage(BaseModel):
    """Segment-final STT. Triggers one moderator turn."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["final_transcript"] = "final_transcript"
    text: str


class AgentTextDeltaMessage(BaseModel):
    """Moderator text delta — render as caption as it streams."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["agent_text_delta"] = "agent_text_delta"
    delta: str


class AgentTextDoneMessage(BaseModel):
    """Moderator turn complete — full text and decision for the client."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["agent_text_done"] = "agent_text_done"
    text: str
    next_action: Literal["followup", "move_on", "clarify", "close"] | None = None
    next_question_id: str | None = None
    interrupted: bool = False


class PhaseChangeMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["phase_change"] = "phase_change"
    phase: Literal["warmup", "active", "closing", "ended"]


class StimulusShowMessage(BaseModel):
    """Tell the client to render a specific stimulus in the preview frame.

    When the stimulus is part of a :class:`ConceptBlock` rotation, the
    concept progress fields let the client render the "Concept N of M"
    chip (PRODUCT.md §3.5 — participants see a number, never the
    internal ``concept.label``).
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["stimulus_show"] = "stimulus_show"
    stimulus_id: str
    kind: Literal["image", "video", "text", "pdf", "link"]
    content: dict[str, Any]
    # Concept Testing 2.0 progress fields — all optional.
    concept_index: int | None = None          # 0-based position in rotation
    concept_count: int | None = None          # total concepts in this block
    block_title: str | None = None            # internal title (researcher-facing)


class BargeInAcceptedMessage(BaseModel):
    """Server accepted a barge-in; TTS/moderator have been cancelled."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["barge_in_accepted"] = "barge_in_accepted"


class BotStartedSpeakingMessage(BaseModel):
    """TTS began emitting audio for this turn — client can show the
    PTT button in "interrupt" state."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["bot_started_speaking"] = "bot_started_speaking"


class BotStoppedSpeakingMessage(BaseModel):
    """TTS drained audio for this turn — client can show the PTT button
    back in "start speaking" state."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["bot_stopped_speaking"] = "bot_stopped_speaking"


class ErrorMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["error"] = "error"
    code: str
    message: str


class PongMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["pong"] = "pong"


ServerMessage = Annotated[
    Union[
        SessionReadyMessage,
        PartialTranscriptMessage,
        FinalTranscriptMessage,
        AgentTextDeltaMessage,
        AgentTextDoneMessage,
        PhaseChangeMessage,
        StimulusShowMessage,
        BargeInAcceptedMessage,
        BotStartedSpeakingMessage,
        BotStoppedSpeakingMessage,
        ErrorMessage,
        PongMessage,
    ],
    Field(discriminator="type"),
]


def parse_client_message(raw: dict[str, Any]) -> ClientMessage:
    """Validate an inbound WS text message. Raises ValidationError on shape mismatch."""
    from pydantic import TypeAdapter

    adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)
    return adapter.validate_python(raw)


__all__ = [
    # client
    "ClientMessage",
    "SessionStartMessage",
    "PttSpeakingStartMessage",
    "PttSpeakingEndMessage",
    "TextInputMessage",
    "AttachmentUploadedMessage",
    "InterruptionMessage",
    "PingMessage",
    # server
    "ServerMessage",
    "SessionReadyMessage",
    "PartialTranscriptMessage",
    "FinalTranscriptMessage",
    "AgentTextDeltaMessage",
    "AgentTextDoneMessage",
    "PhaseChangeMessage",
    "StimulusShowMessage",
    "BargeInAcceptedMessage",
    "BotStartedSpeakingMessage",
    "BotStoppedSpeakingMessage",
    "ErrorMessage",
    "PongMessage",
    # helpers
    "parse_client_message",
]
