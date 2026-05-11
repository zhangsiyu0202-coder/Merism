"""ModeratorLLMProcessor — voice pipeline entry into the moderator runner.

Replaces the generic :class:`LLMProcessor` for sessions attached to a
Merism InterviewGuide. Each inbound :class:`TranscriptionFrame` is
forwarded to :func:`merism.conductor.moderator.stream_turn`, which:

- Reads the current :class:`ExecutionState` from the session
- Makes **one** LLM call that returns both the spoken reply and a
  structured ``ModeratorDecision`` via function calling
- Applies the decision (mark_answered / mark_followup_used / phase)
- Writes user_turn / model_reply / decision rows to ``SessionEvent``

This processor only cares about the spoken text stream — the decision
handling is the moderator's job, invisible on the wire.

Cancellation: on :class:`InterruptionFrame` we flip a flag; the next
iteration of the async generator returns early. The moderator has
already read/written DB state for the partial turn, which is fine —
``transcript_helpers.get_transcript_text`` + the event log both tolerate
a truncated last assistant reply.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from asgiref.sync import sync_to_async

from merism.conductor.moderator import stream_turn
from merism.voice.frames import (
    CancelFrame,
    EndFrame,
    Frame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    StartFrame,
    TranscriptionFrame,
)
from merism.voice.pipeline import FrameDirection, FrameProcessor

logger = logging.getLogger(__name__)


class ModeratorLLMProcessor(FrameProcessor):
    """Wire a live voice session to the moderator runner."""

    def __init__(
        self,
        *,
        session_id: str,
        name: str = "ModeratorLLM",
    ) -> None:
        super().__init__(name)
        self._session_id = session_id
        self._cancelled = False
        self._current_response_id: str | None = None
        self._last_assistant_text: str = ""

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        if isinstance(frame, StartFrame):
            await self.push_frame(frame, direction)
            return
        if isinstance(frame, (EndFrame, CancelFrame)):
            await self.push_frame(frame, direction)
            return
        if isinstance(frame, InterruptionFrame):
            self._cancelled = True
            await self.push_frame(frame, direction)
            return
        if isinstance(frame, TranscriptionFrame):
            await self.push_frame(frame, direction)  # transcript recorder sees it
            await self._run_turn(frame.text)
            return
        await self.push_frame(frame, direction)

    async def _run_turn(self, user_text: str) -> None:
        """Drive one moderator turn and push each text delta as a frame."""
        self._cancelled = False

        # Load the session here — re-load each turn so we always read
        # the latest moderator_state even after process restarts.
        session = await self._load_session()
        if session is None:
            logger.warning(
                "voice.moderator.session_missing",
                extra={"session_id": self._session_id},
            )
            return

        response_id = f"resp_{uuid.uuid4().hex[:12]}"
        self._current_response_id = response_id
        await self.push_frame(LLMFullResponseStartFrame(response_id=response_id))

        buffer = ""
        try:
            async for delta in stream_turn(session, participant_message=user_text):
                if self._cancelled:
                    logger.info(
                        "voice.moderator.interrupted",
                        extra={
                            "session_id": self._session_id,
                            "response_id": response_id,
                            "chars_spoken": len(buffer),
                        },
                    )
                    break
                if not delta:
                    continue
                buffer += delta
                await self.push_frame(LLMTextFrame(text=delta, response_id=response_id))
        except Exception as exc:
            logger.exception(
                "voice.moderator.stream_failed",
                extra={"session_id": self._session_id, "response_id": response_id, "error": str(exc)},
            )

        await self.push_frame(LLMFullResponseEndFrame(response_id=response_id))
        self._current_response_id = None
        self._last_assistant_text = buffer

    async def _load_session(self) -> Any:
        """Fetch the session with related models for moderator access."""
        from merism.models import InterviewSession

        def _fetch() -> Any:
            return (
                InterviewSession.objects.select_related("study", "guide", "participation")
                .filter(id=self._session_id)
                .first()
            )

        return await sync_to_async(_fetch)()

    def truncate_last_assistant(self, up_to_chars: int) -> None:
        """Trim the last assistant turn (ConversationState protocol hook).

        For Merism voice sessions the source of truth lives in the DB
        (transcript + SessionEvent). The truncation here is
        best-effort on the in-memory marker only; the recorder writes
        the truncated-aware transcript row.
        """
        self._last_assistant_text = self._last_assistant_text[:up_to_chars]
