"""Interview moderator processor for pipecat pipeline.

Receives TranscriptionFrame (participant speech), calls the conductor
moderator for a response, emits TextFrame chunks for TTS.
"""

from __future__ import annotations

import asyncio
import logging

from pipecat.frames.frames import (
    Frame,
    TextFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from merism.models import InterviewSession

logger = logging.getLogger(__name__)


class ModeratorProcessor(FrameProcessor):
    """Bridges pipecat pipeline to merism.conductor.moderator.

    On receiving a TranscriptionFrame:
    1. Calls stream_turn() which yields text chunks
    2. Pushes each chunk as a TextFrame for TTS
    """

    def __init__(self, *, session: InterviewSession, **kwargs):
        super().__init__(name="Moderator", **kwargs)
        self._session = session
        self._processing = False

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            if self._processing:
                return  # Skip overlapping turns
            await self._handle_turn(frame.text)
        else:
            await self.push_frame(frame, direction)

    async def _handle_turn(self, user_text: str):
        """Run one moderator turn and stream text to TTS."""
        from merism.conductor.moderator import stream_turn

        self._processing = True
        try:
            # Refresh session from DB
            await asyncio.to_thread(self._session.refresh_from_db)

            async for chunk in stream_turn(self._session, participant_message=user_text):
                if chunk:
                    await self.push_frame(TextFrame(text=chunk))

            # Persist session state
            await asyncio.to_thread(self._session.save)

        except Exception as exc:
            logger.exception("moderator_processor.turn_failed")
            await self.push_frame(TextFrame(text="抱歉，我遇到了一些问题。请再说一次。"))
        finally:
            self._processing = False
