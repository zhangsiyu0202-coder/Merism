"""Pipecat ``FrameProcessor`` driving a v3 LangGraph interview over voice.

Per docs/specs/conductor-v3/design.md §13. The processor is a thin bridge:

- ``StartFrame``: bootstrap — load outline + resolve ``follow_up_mode``,
  then call ``start_interview`` (or resume from existing checkpoint),
  push the first question's text as an ``LLMTextFrame`` trio for TTS.
- ``TranscriptionFrame``: cancel idle timer, call ``answer_interview``,
  emit the next question or finalize.
- ``EndFrame`` / ``CancelFrame``: cancel idle timer.
- 60s idle (timer owned here, not by the graph): synthesize empty
  ``answer_interview`` so the judge can either re-probe or skip per Req 22.

Voice barge-in (``InterruptionFrame``) handling stays in pipecat's frame
layer — we don't feed audio events to the graph directly.

**Decoupling**: the compiled graph is injected via the constructor.
Callers (``merism.realtime.voice``) get the graph from
:func:`merism.conductor.factory.get_graph` and pass it explicitly.
This keeps voice mode independent of HTTP-mode wiring — changes to
``text_adapter.py`` cannot break voice mode.
"""
# ruff: noqa: RUF001

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any

from asgiref.sync import sync_to_async

from merism.conductor.persistence import finalize_to_session
from merism.conductor.runner import (
    answer_interview,
    get_interrupt_payload,
    graph_config,
    start_interview,
)
from merism.conductor.session_outline import get_session_outline
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
    UserStoppedSpeakingFrame,
)
from merism.voice.pipeline import FrameDirection, FrameProcessor

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Safety-net timeout for the buffered-transcription flush. In PTT mode,
# the user explicitly marks turn end by releasing the PTT button — we
# get a ``UserStoppedSpeakingFrame`` and flush immediately. The timer
# below only fires if that frame is somehow lost (network drop, browser
# crash). A long window (30 s) avoids the previous bug where a 3 s
# silence-debounce submitted prematurely while the user was still
# holding PTT and thinking — the AI then "interrupted" by speaking the
# next question. Real abandoned sessions are reaped by the
# 2-hour-idle ``abandon_stuck_sessions`` Celery task.
_DEBOUNCE_SECONDS = 30.0


class ModeratorProcessor(FrameProcessor):
    """Bridge a voice session to the v3 LangGraph interview engine.

    The compiled ``graph`` is injected by the caller; the processor does
    not reach into module-level singletons. This lets tests run with a
    private graph (e.g. ``InMemorySaver``) and lets production wire a
    voice-specific graph instance separate from the HTTP text adapter.
    """

    def __init__(
        self,
        *,
        session_id: str,
        graph: Any | None = None,
        debounce_seconds: float = _DEBOUNCE_SECONDS,
        name: str = "Moderator",
    ) -> None:
        super().__init__(name)
        self._session_id = session_id
        self._debounce_seconds = debounce_seconds
        self._bootstrapped = False
        # Buffer of partial-turn transcription text. Populated by every
        # TranscriptionFrame; flushed after ``_debounce_seconds`` of
        # silence (or on InterruptionFrame). One graph turn = one flush.
        self._pending_text: list[str] = []
        self._flush_task: asyncio.Task | None = None
        # Lazy graph resolution — if not injected, fetch from factory at
        # bootstrap time. Tests inject a private graph; production wires
        # the factory-built shared instance.
        self._graph = graph

    def _resolve_graph(self) -> Any:
        if self._graph is None:
            from merism.conductor.factory import get_graph

            self._graph = get_graph()
        return self._graph

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        if isinstance(frame, StartFrame):
            await self.push_frame(frame, direction)
            if not self._bootstrapped:
                self._bootstrapped = True
                await self._bootstrap()
            return
        if isinstance(frame, (EndFrame, CancelFrame)):
            await self._cancel_flush_timer()
            await self.push_frame(frame, direction)
            return
        if isinstance(frame, InterruptionFrame):
            # Barge-in: drop any buffered transcription (it was for a
            # previous question we're abandoning).
            self._pending_text.clear()
            await self._cancel_flush_timer()
            await self.push_frame(frame, direction)
            return
        if isinstance(frame, UserStoppedSpeakingFrame):
            # PTT released — the user has explicitly marked the turn
            # boundary. Flush the buffered transcription immediately
            # rather than waiting for the safety-net timer. Without
            # this, a user holding PTT and pausing to think for >3 s
            # caused the timer to fire and the AI to speak over them
            # (Bug 2026-05-24: "AI 会打断我说话").
            await self.push_frame(frame, direction)
            await self._cancel_flush_timer()
            if self._pending_text:
                joined = " ".join(self._pending_text).strip()
                self._pending_text = []
                if joined:
                    await self._submit_answer(joined)
            return
        if isinstance(frame, TranscriptionFrame):
            await self.push_frame(frame, direction)  # let recorder see it
            self._pending_text.append(frame.text)
            self._reschedule_flush()
            return
        await self.push_frame(frame, direction)

    # ── Lifecycle ──

    async def _bootstrap(self) -> None:
        """First-time start: load session + outline, kick off graph.

        On reconnect (the participant's WebSocket dropped and reconnected
        — same session_id, fresh ``ModeratorProcessor`` instance), the
        LangGraph checkpointer already has state for this thread_id.
        Calling ``start_interview`` again would re-invoke the graph from
        the initial state and push Q1 to TTS a second time — the
        participant would hear the greeting again every time their
        connection blipped, and the transcript would accumulate
        duplicate assistant turns. We detect this by inspecting the
        checkpoint and skip the bootstrap entirely on reconnect: the
        participant already heard the current question; just wait for
        their next answer.

        Same pattern as :func:`merism.conductor.text_adapter._is_first_turn`.
        """
        session = await self._load_session()
        if session is None:
            logger.error("conductor.voice.bootstrap.session_not_found %s", self._session_id)
            return
        try:
            outline = get_session_outline(session)
        except Exception:
            logger.exception("conductor.voice.bootstrap.invalid_outline")
            return

        graph = self._resolve_graph()

        is_first = await sync_to_async(self._checkpoint_is_empty)(graph)
        if not is_first:
            # Reconnect — graph is mid-interview at an interrupt(). The
            # participant already heard the current question over their
            # previous WS connection; pushing it again would duplicate
            # it through TTS and into the transcript. Just wait for the
            # next user answer.
            logger.info(
                "conductor.voice.bootstrap.reconnect session=%s",
                self._session_id,
            )
            return

        result = await sync_to_async(start_interview)(
            graph,
            outline=outline,
            thread_id=self._session_id,
            follow_up_mode=session.follow_up_mode,  # type: ignore[arg-type]
        )
        await self._handle_graph_result(result)

    def _checkpoint_is_empty(self, graph: Any) -> bool:
        """True iff there is no LangGraph checkpoint for this session.

        ``True`` → fresh session, call ``start_interview``.
        ``False`` → reconnect, the participant has already heard the
        current question; do not re-fire the graph.
        """
        state = graph.get_state(graph_config(self._session_id))
        if state is None:
            return True
        return not state.values

    async def _submit_answer(self, user_text: str) -> None:
        graph = self._resolve_graph()
        try:
            result = await sync_to_async(answer_interview)(graph, user_answer=user_text, thread_id=self._session_id)
        except Exception:
            logger.exception("conductor.voice.answer.failed")
            return
        await self._handle_graph_result(result)

    async def _handle_graph_result(self, result: dict) -> None:
        payload = get_interrupt_payload(result)
        if payload is not None:
            question_text = payload.get("question") or ""
            if question_text:
                await self._push_assistant_text(question_text)
            # No idle timer: the moderator simply waits for the user.
            # If the participant never replies, the session-level
            # abandon_stuck_sessions Celery task (2-hour idle, in
            # ``merism.conductor.closure``) handles cleanup.
            return

        # No interrupt → graph reached END. Persist terminal state;
        # post_session pipeline produces the actual report. Speak a
        # brief closing for the participant (no LLM-generated report
        # over TTS — too long for voice).
        await finalize_to_session(self._resolve_graph(), self._session_id)
        await self._push_assistant_text("感谢你的参与，访谈到此结束。")

    async def _push_assistant_text(self, text: str) -> None:
        """Emit the standard LLM frame trio so TTS consumes it cleanly."""
        await self.push_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
        await self.push_frame(LLMTextFrame(text), FrameDirection.DOWNSTREAM)
        await self.push_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

    # ── Transcription debounce ──

    def _reschedule_flush(self) -> None:
        """Restart the post-utterance flush timer.

        Each TranscriptionFrame appends to ``_pending_text`` and calls
        this. The timer fires ``_flush_pending`` after
        ``_debounce_seconds`` of silence (no new transcription arrived).
        Coalesces sentence-segmented STT events into one graph turn.
        """
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
        self._flush_task = asyncio.create_task(self._flush_after(self._debounce_seconds))

    async def _cancel_flush_timer(self) -> None:
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._flush_task
        self._flush_task = None

    async def _flush_after(self, seconds: float) -> None:
        try:
            await asyncio.sleep(seconds)
        except asyncio.CancelledError:
            return
        if not self._pending_text:
            return
        # Join with single spaces — Paraformer already emits with the
        # right punctuation per sentence; we're stitching sentence-level
        # finals into one answer.
        joined = " ".join(self._pending_text).strip()
        self._pending_text = []
        if joined:
            await self._submit_answer(joined)

    # ── Helpers ──

    async def _load_session(self):
        from merism.models import InterviewSession

        try:
            return await sync_to_async(
                lambda: InterviewSession.objects.select_related("guide").get(id=self._session_id)
            )()
        except Exception:
            logger.exception("conductor.voice.load_session.failed")
            return None


__all__ = ["ModeratorProcessor"]
