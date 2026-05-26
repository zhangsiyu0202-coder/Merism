"""ModeratorProcessor — transcription-frame debounce coalescing.

Bug context (2026-05-24): Paraformer STT emits ``is_final=True`` per
**sentence**, so a single user turn that spans natural pauses lands as
2-3 ``TranscriptionFrame``s. The pre-fix moderator submitted each one
as its own graph turn, causing premature ``advance`` to the next
outline question while the user was still talking.

The fix: buffer transcription frames in a list, restart a flush timer
on every frame; only flush (call ``_submit_answer`` once with the
joined text) after ``debounce_seconds`` of silence.
"""
# ruff: noqa: RUF001

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from merism.voice.frames import (
    InterruptionFrame,
    StartFrame,
    TranscriptionFrame,
)
from merism.voice.processors.moderator import ModeratorProcessor


def _make_processor(*, debounce_seconds: float = 0.05) -> tuple[ModeratorProcessor, AsyncMock]:
    """Build a moderator with a fast debounce + mocked submit/bootstrap.

    We stub ``_bootstrap`` (no graph, no DB) and ``_submit_answer`` so
    the test can count flushes without hitting LangGraph.
    """
    proc = ModeratorProcessor(
        session_id="test-session",
        graph=object(),  # truthy, never invoked because _submit_answer is mocked
        debounce_seconds=debounce_seconds,
    )
    proc._bootstrap = AsyncMock()  # type: ignore[method-assign]
    submit_mock = AsyncMock()
    proc._submit_answer = submit_mock  # type: ignore[method-assign]
    return proc, submit_mock


class _FakeDirection:
    """Stand-in for FrameDirection — the moderator only uses it to push."""

    DOWNSTREAM = "downstream"


@pytest.mark.asyncio
class TestModeratorTranscriptionDebounce:
    async def test_single_frame_flushes_once(self) -> None:
        proc, submit = _make_processor(debounce_seconds=0.05)
        await proc.process_frame(StartFrame(), _FakeDirection.DOWNSTREAM)

        await proc.process_frame(
            TranscriptionFrame(text="我比较看重音质"),
            _FakeDirection.DOWNSTREAM,
        )
        # Wait past the debounce window
        await asyncio.sleep(0.15)

        submit.assert_awaited_once_with("我比较看重音质")

    async def test_two_frames_within_debounce_coalesce(self) -> None:
        """The actual bug: two sentences from one user turn → one submit."""
        proc, submit = _make_processor(debounce_seconds=0.1)
        await proc.process_frame(StartFrame(), _FakeDirection.DOWNSTREAM)

        await proc.process_frame(
            TranscriptionFrame(text="我比较看重音质"),
            _FakeDirection.DOWNSTREAM,
        )
        await asyncio.sleep(0.03)
        await proc.process_frame(
            TranscriptionFrame(text="另外品牌也很重要"),
            _FakeDirection.DOWNSTREAM,
        )
        # Wait past the debounce window — only the second frame's timer
        # should fire (the first was cancelled by the second arrival).
        await asyncio.sleep(0.2)

        submit.assert_awaited_once()
        joined = submit.await_args.args[0]
        assert "音质" in joined and "品牌" in joined

    async def test_ptt_release_flushes_immediately(self) -> None:
        """``UserStoppedSpeakingFrame`` (PTT release) flushes whatever's
        in the buffer right away — without waiting for the safety-net
        timer. This is the primary turn-boundary signal in PTT mode.

        Bug context (2026-05-24): the previous 3 s silence debounce
        flushed prematurely when the user paused while still holding
        PTT to think, causing the AI to speak the next question over
        them ("AI 会打断我说话"). The fix is to treat PTT release as
        the explicit turn-end signal.
        """
        from merism.voice.frames import UserStoppedSpeakingFrame

        # Long safety-net debounce — the test asserts we DO NOT wait
        # for it; we flush on PTT release instead.
        proc, submit = _make_processor(debounce_seconds=10.0)
        await proc.process_frame(StartFrame(), _FakeDirection.DOWNSTREAM)

        await proc.process_frame(
            TranscriptionFrame(text="我经常出差"),
            _FakeDirection.DOWNSTREAM,
        )
        # User releases PTT — server queues UserStoppedSpeakingFrame.
        await proc.process_frame(
            UserStoppedSpeakingFrame(),
            _FakeDirection.DOWNSTREAM,
        )
        # Asserting before the long timer would fire — flush must be
        # synchronous on PTT release.
        await asyncio.sleep(0.05)

        submit.assert_awaited_once_with("我经常出差")

    async def test_ptt_release_with_empty_buffer_no_submit(self) -> None:
        """If the user releases PTT without saying anything (or STT
        suppressed all of it as noise), don't submit an empty turn —
        otherwise the judge gets a fake `""` answer to evaluate.
        """
        from merism.voice.frames import UserStoppedSpeakingFrame

        proc, submit = _make_processor(debounce_seconds=10.0)
        await proc.process_frame(StartFrame(), _FakeDirection.DOWNSTREAM)
        await proc.process_frame(
            UserStoppedSpeakingFrame(),
            _FakeDirection.DOWNSTREAM,
        )
        await asyncio.sleep(0.05)

        submit.assert_not_awaited()

    async def test_ptt_release_after_pause_does_not_submit_twice(self) -> None:
        """A user holding PTT for a few seconds, pausing to think,
        then releasing must produce ONE submit (no premature timer fire
        + a duplicate flush on release).
        """
        from merism.voice.frames import UserStoppedSpeakingFrame

        proc, submit = _make_processor(debounce_seconds=10.0)
        await proc.process_frame(StartFrame(), _FakeDirection.DOWNSTREAM)

        await proc.process_frame(
            TranscriptionFrame(text="嗯，我想想"),
            _FakeDirection.DOWNSTREAM,
        )
        # Long pause inside the same PTT session — would have fired
        # the old 3 s debounce. Asserts the new 30 s safety-net does
        # NOT fire here (we're well under it).
        await asyncio.sleep(0.5)
        await proc.process_frame(
            TranscriptionFrame(text="主要是因为价格"),
            _FakeDirection.DOWNSTREAM,
        )
        # User releases PTT.
        await proc.process_frame(
            UserStoppedSpeakingFrame(),
            _FakeDirection.DOWNSTREAM,
        )
        await asyncio.sleep(0.05)

        submit.assert_awaited_once()
        joined = submit.await_args.args[0]
        assert "我想想" in joined and "价格" in joined


    async def test_two_frames_outside_debounce_fire_separately(self) -> None:
        """Two true turns (long pause between) → two submits."""
        proc, submit = _make_processor(debounce_seconds=0.05)
        await proc.process_frame(StartFrame(), _FakeDirection.DOWNSTREAM)

        await proc.process_frame(
            TranscriptionFrame(text="第一句"),
            _FakeDirection.DOWNSTREAM,
        )
        await asyncio.sleep(0.15)  # past debounce → flushes
        await proc.process_frame(
            TranscriptionFrame(text="第二句"),
            _FakeDirection.DOWNSTREAM,
        )
        await asyncio.sleep(0.15)  # past debounce → flushes again

        assert submit.await_count == 2
        first_call_text = submit.await_args_list[0].args[0]
        second_call_text = submit.await_args_list[1].args[0]
        assert "第一句" in first_call_text
        assert "第二句" in second_call_text

    async def test_interruption_drops_buffer(self) -> None:
        """User barges in mid-question → buffer cleared, no submit."""
        proc, submit = _make_processor(debounce_seconds=0.1)
        await proc.process_frame(StartFrame(), _FakeDirection.DOWNSTREAM)

        await proc.process_frame(
            TranscriptionFrame(text="abandoned text"),
            _FakeDirection.DOWNSTREAM,
        )
        await proc.process_frame(InterruptionFrame(), _FakeDirection.DOWNSTREAM)
        await asyncio.sleep(0.2)

        submit.assert_not_awaited()

    async def test_no_idle_timer_after_question(self) -> None:
        """No idle-timeout mechanism. The moderator waits indefinitely
        for the user; it must NEVER auto-submit an empty answer just
        because the user is silent. Earlier code had a 60s timer that
        polluted transcripts with fake "" turns.
        """
        proc, submit = _make_processor(debounce_seconds=0.05)
        await proc.process_frame(StartFrame(), _FakeDirection.DOWNSTREAM)

        # 3 seconds of total silence after the bot question. With the
        # 60s idle timer this would still be safe, but the test exists
        # to lock in the contract: no _submit_answer() unless the user
        # actually said something.
        await asyncio.sleep(3.0)

        submit.assert_not_awaited()


@pytest.mark.asyncio
class TestModeratorReconnect:
    """Bug context (2026-05-24): when a participant's WebSocket dropped
    and reconnected, a fresh ``ModeratorProcessor`` was created with
    ``_bootstrapped=False``. Bootstrap unconditionally called
    ``start_interview``, which re-invoked the LangGraph from the initial
    state and pushed Q1 to TTS again — the participant heard the
    greeting on every reconnect and the transcript filled with duplicate
    assistant turns. The fix: detect existing checkpoints via
    ``graph.get_state`` and skip the bootstrap on reconnect.
    """

    async def test_reconnect_does_not_re_fire_start_interview(self) -> None:
        """Reconnect path: checkpoint is non-empty → skip start_interview."""
        from unittest.mock import MagicMock, patch

        proc = ModeratorProcessor(
            session_id="reconnect-session",
            graph=MagicMock(),
            debounce_seconds=0.05,
        )
        # Stub the session loader + outline lookup so the test stays
        # ORM-free.
        proc._load_session = AsyncMock(return_value=MagicMock(follow_up_mode="standard"))  # type: ignore[method-assign]

        # Existing checkpoint state: state.values is a non-empty dict.
        existing_state = MagicMock()
        existing_state.values = {"section_i": 1, "question_i": 0}
        proc._graph.get_state.return_value = existing_state

        push_assistant = AsyncMock()
        proc._push_assistant_text = push_assistant  # type: ignore[method-assign]

        with patch("merism.voice.processors.moderator.start_interview") as mock_start, patch(
            "merism.voice.processors.moderator.get_session_outline",
            return_value=MagicMock(),
        ):
            await proc._bootstrap()

        # The reconnect path skips the graph entirely.
        mock_start.assert_not_called()
        push_assistant.assert_not_called()

    async def test_fresh_session_calls_start_interview(self) -> None:
        """Fresh session path: no checkpoint → ``start_interview`` runs."""
        from unittest.mock import MagicMock, patch

        proc = ModeratorProcessor(
            session_id="fresh-session",
            graph=MagicMock(),
            debounce_seconds=0.05,
        )
        proc._load_session = AsyncMock(return_value=MagicMock(follow_up_mode="standard"))  # type: ignore[method-assign]

        # No state yet — checkpoint returns ``None`` (or empty values).
        proc._graph.get_state.return_value = None

        push_assistant = AsyncMock()
        proc._push_assistant_text = push_assistant  # type: ignore[method-assign]

        # ``start_interview`` returns a result with an interrupt
        # payload; the moderator should push the question text.
        fake_result = {
            "__interrupt__": [MagicMock(value={"question": "Q1 hello"})],
        }
        with patch(
            "merism.voice.processors.moderator.start_interview",
            return_value=fake_result,
        ) as mock_start, patch(
            "merism.voice.processors.moderator.get_session_outline",
            return_value=MagicMock(),
        ):
            await proc._bootstrap()

        mock_start.assert_called_once()
        push_assistant.assert_called_once_with("Q1 hello")
