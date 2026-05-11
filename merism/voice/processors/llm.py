"""LLM FrameProcessor — streams LLM tokens into ``LLMTextFrame``s.

Consumes :class:`TranscriptionFrame`; on each one, pushes:
- :class:`LLMFullResponseStartFrame` (with fresh ``response_id``)
- :class:`LLMTextFrame` × N (each tagged with ``response_id``)
- :class:`LLMFullResponseEndFrame` (same ``response_id``)

Keeps a bounded rolling context so turns stay in character without
shipping the whole conversation every time.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from merism.memai.llm import default_model, get_llm
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


class LLMProcessor(FrameProcessor):
    """Converts a final transcription into a streamed LLM reply."""

    def __init__(
        self,
        *,
        system_prompt: str,
        model: str | None = None,
        max_tokens: int = 400,
        context_window: int = 12,
        name: str = "LLM",
        team: Any | None = None,
        trace_id: Any | None = None,
    ) -> None:
        super().__init__(name)
        self._system_prompt = system_prompt
        self._model = model or default_model()
        self._max_tokens = max_tokens
        self._team = team
        self._trace_id = trace_id
        self._context_window = context_window
        self._history: list[dict[str, str]] = []
        self._cancelled = False
        self._current_response_id: str | None = None

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
            await self.push_frame(frame, direction)  # recorder sees user turn
            await self._generate_reply(frame.text)
            return

        await self.push_frame(frame, direction)

    async def _generate_reply(self, user_text: str) -> None:
        self._cancelled = False
        self._history.append({"role": "user", "content": user_text})
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._system_prompt},
            *self._history[-self._context_window :],
        ]

        client = get_llm()
        gw_client = None
        if self._team and self._trace_id:
            try:
                from merism.llm_gateway.client import sync_get_client

                gw_client = sync_get_client("chat", team=self._team, trace_id=self._trace_id)
            except Exception:
                pass

        try:
            if gw_client:
                stream = gw_client.sync_stream(
                    messages=messages, max_tokens=self._max_tokens,
                )
            else:
                stream = client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    stream=True,
                    max_tokens=self._max_tokens,
                )
        except Exception as exc:
            logger.warning("voice.llm.create_failed", extra={"error": str(exc)})
            return

        response_id = f"resp_{uuid.uuid4().hex[:12]}"
        self._current_response_id = response_id
        await self.push_frame(LLMFullResponseStartFrame(response_id=response_id))

        assistant_reply = ""
        for chunk in stream:
            if self._cancelled:
                break
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if not delta:
                continue
            assistant_reply += delta
            await self.push_frame(LLMTextFrame(text=delta, response_id=response_id))

        await self.push_frame(LLMFullResponseEndFrame(response_id=response_id))
        self._current_response_id = None

        if assistant_reply:
            self._history.append({"role": "assistant", "content": assistant_reply})

    def truncate_last_assistant(self, up_to_chars: int) -> None:
        """Trim the last assistant turn in history to ``up_to_chars``.

        Called by ``ConversationState`` processor when a
        :class:`TruncatedFrame` flows through, so the LLM's future
        context reflects what the user HEARD.
        """
        for i in range(len(self._history) - 1, -1, -1):
            if self._history[i]["role"] == "assistant":
                self._history[i]["content"] = self._history[i]["content"][:up_to_chars]
                return
