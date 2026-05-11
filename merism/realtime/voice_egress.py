"""Bridge between the voice pipeline and the participant's WebSocket.

Pattern: ``dst is None`` on Observer callback means this is the final
push — no more processors downstream — so the observer sees each frame
exactly once without manual deduplication. That's the sole place we
serialise to the wire.

Frame → wire mapping (other frames are dropped silently):

    InterimTranscriptionFrame   → PartialTranscriptMessage
    TranscriptionFrame          → FinalTranscriptMessage
    LLMTextFrame                → AgentTextDeltaMessage
    LLMFullResponseEndFrame     → AgentTextDoneMessage
    TTSAudioRawFrame            → binary frame
    InterruptionFrame           → BargeInAcceptedMessage
    ErrorFrame                  → ErrorMessage
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from merism.realtime.voice_protocol import (
    AgentTextDeltaMessage,
    AgentTextDoneMessage,
    BargeInAcceptedMessage,
    BotStartedSpeakingMessage,
    BotStoppedSpeakingMessage,
    ErrorMessage,
    FinalTranscriptMessage,
    PartialTranscriptMessage,
    StimulusShowMessage,
)
from merism.voice import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    ErrorFrame,
    Frame,
    FrameDirection,
    FrameProcessor,
    InterimTranscriptionFrame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMTextFrame,
    Observer,
    StimulusShowFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
)

if TYPE_CHECKING:
    from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class WebSocketEgressObserver(Observer):
    """Pipeline → ``VoiceConsumer`` egress bridge."""

    def __init__(self, consumer: "AsyncWebsocketConsumer") -> None:
        self._consumer = consumer
        # Accumulate LLM deltas per response_id so we can emit the
        # assembled "done" payload on LLMFullResponseEndFrame.
        self._replies: dict[str, list[str]] = {}
        # Last interruption state — so we can mark AgentTextDoneMessage
        # correctly. Reset at the start of each new response.
        self._current_interrupted_ids: set[str] = set()

    async def on_frame(
        self,
        frame: Frame,
        src: FrameProcessor,
        dst: FrameProcessor | None,
        direction: FrameDirection,
    ) -> None:
        # Only serialise at end-of-pipe (natural dedup).
        if dst is not None:
            return

        if isinstance(frame, InterimTranscriptionFrame):
            await self._send_text(PartialTranscriptMessage(text=frame.text))
            return

        if isinstance(frame, TranscriptionFrame):
            await self._send_text(FinalTranscriptMessage(text=frame.text))
            return

        if isinstance(frame, LLMTextFrame):
            self._replies.setdefault(frame.response_id, []).append(frame.text)
            await self._send_text(AgentTextDeltaMessage(delta=frame.text))
            return

        if isinstance(frame, LLMFullResponseEndFrame):
            parts = self._replies.pop(frame.response_id, [])
            text = "".join(parts)
            interrupted = frame.response_id in self._current_interrupted_ids
            self._current_interrupted_ids.discard(frame.response_id)
            await self._send_text(
                AgentTextDoneMessage(text=text, interrupted=interrupted)
            )
            return

        if isinstance(frame, TTSAudioRawFrame):
            if frame.audio:
                await self._consumer.send(bytes_data=frame.audio)
            return

        if isinstance(frame, BotStartedSpeakingFrame):
            await self._send_text(BotStartedSpeakingMessage())
            return

        if isinstance(frame, BotStoppedSpeakingFrame):
            await self._send_text(BotStoppedSpeakingMessage())
            return

        if isinstance(frame, InterruptionFrame):
            if frame.response_id:
                self._current_interrupted_ids.add(frame.response_id)
            await self._send_text(BargeInAcceptedMessage())
            return

        if isinstance(frame, StimulusShowFrame):
            await self._send_text(
                StimulusShowMessage(
                    stimulus_id=frame.stimulus_id,
                    kind=frame.kind,  # type: ignore[arg-type]
                    content=frame.content,
                    concept_index=frame.concept_index,
                    concept_count=frame.concept_count,
                    block_title=frame.block_title,
                )
            )
            return

        if isinstance(frame, ErrorFrame):
            await self._send_text(
                ErrorMessage(code=frame.code or "pipeline_error", message=frame.message)
            )
            return

    async def _send_text(self, message: object) -> None:
        try:
            await self._consumer.send(text_data=message.model_dump_json())  # type: ignore[attr-defined]
        except Exception as exc:
            logger.warning("voice.egress.send_failed", extra={"error": str(exc)})
