"""ConversationState — OpenAI-Realtime-inspired conversation tracking.

The canonical insight from OpenAI's Realtime API docs + community:
**transcript deltas emit even if audio never plays**. Without
truncation the LLM context shows "I said X" when the user only heard
"I said Y", and all multi-turn logic silently corrupts.

This processor:
- Appends a new :class:`ConversationItem` on each :class:`TranscriptionFrame`
  (role=user) and :class:`LLMFullResponseStartFrame` (role=assistant,
  accumulating :class:`LLMTextFrame` deltas until :class:`...EndFrame`).
- On :class:`TruncatedFrame` — which flows through the pipeline after
  :class:`InterruptionFrame` — it finds the matching response_id item
  and trims its text to the estimated character count corresponding to
  ``audio_played_ms``.
- Exposes :meth:`snapshot` so callers (typically a persistence
  observer) can read the clean history to save.

The char count approximation uses a **speaking rate heuristic** — Qwen
Chinese TTS at 1.0x speed renders roughly 4.5 characters per second
(≈220 ms/char). Tunable via ``chars_per_ms`` if future testing refines
it. A tiny imprecision here is preferable to no truncation at all.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

from merism.voice.frames import (
    CancelFrame,
    EndFrame,
    Frame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    StartFrame,
    TranscriptionFrame,
    TruncatedFrame,
)
from merism.voice.pipeline import FrameDirection, FrameProcessor

logger = logging.getLogger(__name__)


Role = Literal["user", "assistant"]


@dataclass
class ConversationItem:
    id: str
    role: Role
    text: str = ""
    truncated: bool = False
    original_text: str = ""


@dataclass
class ConversationSnapshot:
    items: list[ConversationItem] = field(default_factory=list)


class ConversationState(FrameProcessor):
    """Maintains a canonical, truncation-aware transcript."""

    DEFAULT_CHARS_PER_MS = 0.0045

    def __init__(
        self,
        *,
        chars_per_ms: float = DEFAULT_CHARS_PER_MS,
        name: str = "ConversationState",
    ) -> None:
        super().__init__(name)
        self._chars_per_ms = chars_per_ms
        self._items: list[ConversationItem] = []
        self._open_assistant: ConversationItem | None = None

    def snapshot(self) -> ConversationSnapshot:
        """Return a deep copy of the current conversation (safe to persist)."""
        return ConversationSnapshot(
            items=[
                ConversationItem(
                    id=it.id,
                    role=it.role,
                    text=it.text,
                    truncated=it.truncated,
                    original_text=it.original_text,
                )
                for it in self._items
            ]
        )

    def reset(self) -> None:
        self._items = []
        self._open_assistant = None

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        if isinstance(frame, StartFrame):
            self.reset()
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, (EndFrame, CancelFrame)):
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, TranscriptionFrame):
            self._open_assistant = None
            self._items.append(
                ConversationItem(id=frame.name, role="user", text=frame.text)
            )
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, LLMFullResponseStartFrame):
            item = ConversationItem(id=frame.response_id, role="assistant", text="")
            self._items.append(item)
            self._open_assistant = item
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, LLMTextFrame) and self._open_assistant is not None:
            self._open_assistant.text += frame.text
            self._open_assistant.original_text += frame.text
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, LLMFullResponseEndFrame):
            if self._open_assistant is not None:
                self._open_assistant.original_text = self._open_assistant.text
                self._open_assistant = None
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, TruncatedFrame):
            self._apply_truncation(frame.response_id, frame.audio_played_ms)
            await self.push_frame(frame, direction)
            return

        await self.push_frame(frame, direction)

    def _apply_truncation(self, response_id: str, played_ms: int) -> None:
        for item in reversed(self._items):
            if item.role == "assistant" and item.id == response_id:
                if not item.original_text:
                    item.original_text = item.text
                keep_chars = max(0, int(played_ms * self._chars_per_ms))
                truncated_text = item.text[:keep_chars]
                logger.info(
                    "voice.conversation.truncate",
                    extra={
                        "response_id": response_id,
                        "played_ms": played_ms,
                        "kept_chars": len(truncated_text),
                        "original_chars": len(item.original_text),
                    },
                )
                item.text = truncated_text
                item.truncated = True
                return
        logger.warning(
            "voice.conversation.truncate_no_match",
            extra={"response_id": response_id},
        )
