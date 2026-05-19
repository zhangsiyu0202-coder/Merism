"""UserIdleDetector — prompts the moderator after prolonged user silence."""

from __future__ import annotations

import asyncio
import logging

from merism.voice.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    CancelFrame,
    EndFrame,
    Frame,
    StartFrame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from merism.voice.pipeline import FrameDirection, FrameProcessor

logger = logging.getLogger(__name__)


class UserIdleDetector(FrameProcessor):
    def __init__(
        self,
        *,
        idle_seconds: float = 12.0,
        prompt_text: str = "(user has been silent)",
        max_prompts: int = 2,
        name: str = "UserIdleDetector",
    ) -> None:
        super().__init__(name)
        self._idle_seconds = idle_seconds
        self._prompt_text = prompt_text
        self._max_prompts = max_prompts
        self._prompts_fired = 0
        self._timer_task: asyncio.Task[None] | None = None
        self._bot_speaking = False
        self._user_speaking = False

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        if isinstance(frame, StartFrame):
            self._reset_timer()
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, (EndFrame, CancelFrame)):
            self._cancel_timer()
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, UserStartedSpeakingFrame):
            self._user_speaking = True
            self._prompts_fired = 0
            self._cancel_timer()
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, UserStoppedSpeakingFrame):
            self._user_speaking = False
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, BotStartedSpeakingFrame):
            self._bot_speaking = True
            self._cancel_timer()
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, BotStoppedSpeakingFrame):
            self._bot_speaking = False
            self._reset_timer()
            await self.push_frame(frame, direction)
            return

        await self.push_frame(frame, direction)

    def _reset_timer(self) -> None:
        self._cancel_timer()
        self._timer_task = asyncio.create_task(self._fire_on_idle())

    def _cancel_timer(self) -> None:
        if self._timer_task is not None:
            self._timer_task.cancel()
            self._timer_task = None

    async def _fire_on_idle(self) -> None:
        try:
            await asyncio.sleep(self._idle_seconds)
        except asyncio.CancelledError:
            return
        if self._user_speaking or self._bot_speaking:
            return
        if self._prompts_fired >= self._max_prompts:
            logger.info(
                "voice.idle.budget_exhausted",
                extra={"fired": self._prompts_fired, "max": self._max_prompts},
            )
            return
        self._prompts_fired += 1
        logger.info("voice.idle.prompt", extra={"idle_seconds": self._idle_seconds})
        await self.push_frame(TranscriptionFrame(text=self._prompt_text))
