"""Tests for ConversationState + TruncatedFrame semantics.

The correctness property we're fencing:

    Given an LLM that generated "Hello world, how are you today?"
    but the user barged in after hearing "Hello wo" (≈ 400 ms),
    ConversationState.snapshot().items[-1].text must be "Hello wo",
    NOT the full generated string.

Without this, multi-turn LLM context thinks it said X when the user
only heard Y, and all follow-ups drift.
"""

from __future__ import annotations

import asyncio

import pytest

from merism.voice import (
    EndFrame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    Pipeline,
    PipelineTask,
    TranscriptionFrame,
    TruncatedFrame,
)
from merism.voice.processors.conversation_state import ConversationState


@pytest.mark.asyncio
async def test_clean_turn_stored_in_full() -> None:
    """No interruption → text stored verbatim."""
    cs = ConversationState()
    task = PipelineTask(Pipeline([cs]))

    await task.start()
    await task.queue_frame(TranscriptionFrame(text="how are you today?"))
    await task.queue_frame(LLMFullResponseStartFrame(response_id="resp_1"))
    await task.queue_frame(LLMTextFrame(text="I'm doing ", response_id="resp_1"))
    await task.queue_frame(LLMTextFrame(text="great, thanks for asking!", response_id="resp_1"))
    await task.queue_frame(LLMFullResponseEndFrame(response_id="resp_1"))
    await asyncio.sleep(0.05)
    await task.queue_frame(EndFrame())
    await asyncio.sleep(0.05)
    await task.stop()

    snapshot = cs.snapshot()
    assert len(snapshot.items) == 2
    assert snapshot.items[0].role == "user"
    assert snapshot.items[0].text == "how are you today?"
    assert snapshot.items[1].role == "assistant"
    assert snapshot.items[1].text == "I'm doing great, thanks for asking!"
    assert snapshot.items[1].truncated is False


@pytest.mark.asyncio
async def test_truncation_trims_history_to_what_was_heard() -> None:
    """TruncatedFrame with played_ms = 400 → ~1.8 chars kept at default rate."""
    # Use a higher chars_per_ms so the test doesn't depend on exact Qwen rate.
    # 0.02 chars/ms → 400 ms = 8 chars kept.
    cs = ConversationState(chars_per_ms=0.02)
    task = PipelineTask(Pipeline([cs]))

    await task.start()
    await task.queue_frame(TranscriptionFrame(text="hi"))
    await task.queue_frame(LLMFullResponseStartFrame(response_id="resp_42"))
    await task.queue_frame(
        LLMTextFrame(text="Hello world, how are you today?", response_id="resp_42")
    )
    await task.queue_frame(LLMFullResponseEndFrame(response_id="resp_42"))
    await asyncio.sleep(0.05)

    # Simulate barge-in: user heard 400 ms of audio.
    await task.queue_frame(
        TruncatedFrame(response_id="resp_42", audio_played_ms=400)
    )
    await asyncio.sleep(0.05)

    await task.queue_frame(EndFrame())
    await asyncio.sleep(0.05)
    await task.stop()

    snapshot = cs.snapshot()
    assert len(snapshot.items) == 2
    assistant = snapshot.items[1]
    assert assistant.truncated is True
    assert assistant.text == "Hello wo"
    # Original is still available for diagnostics / full-transcript export.
    assert assistant.original_text == "Hello world, how are you today?"


@pytest.mark.asyncio
async def test_truncation_with_unknown_response_id_is_a_noop_with_warning() -> None:
    """Misdirected TruncatedFrame: keep going, don't crash."""
    cs = ConversationState()
    task = PipelineTask(Pipeline([cs]))

    await task.start()
    await task.queue_frame(TranscriptionFrame(text="hi"))
    await task.queue_frame(LLMFullResponseStartFrame(response_id="resp_1"))
    await task.queue_frame(LLMTextFrame(text="hello", response_id="resp_1"))
    await task.queue_frame(LLMFullResponseEndFrame(response_id="resp_1"))
    await asyncio.sleep(0.05)

    # Wrong ID — should not mutate anything.
    await task.queue_frame(
        TruncatedFrame(response_id="resp_nonexistent", audio_played_ms=500)
    )
    await asyncio.sleep(0.05)

    await task.queue_frame(EndFrame())
    await asyncio.sleep(0.05)
    await task.stop()

    snapshot = cs.snapshot()
    assistant = snapshot.items[1]
    assert assistant.text == "hello"
    assert assistant.truncated is False


@pytest.mark.asyncio
async def test_interruption_frame_without_matching_truncate_does_not_alter_history() -> None:
    """InterruptionFrame alone (no TruncatedFrame) should NOT mutate transcript.

    In production TTSProcessor emits TruncatedFrame right after Interruption.
    If for some reason Truncate never arrives (e.g. no response in flight),
    the state must be untouched.
    """
    cs = ConversationState(chars_per_ms=0.02)
    task = PipelineTask(Pipeline([cs]))

    await task.start()
    await task.queue_frame(TranscriptionFrame(text="hi"))
    await task.queue_frame(LLMFullResponseStartFrame(response_id="resp_1"))
    await task.queue_frame(LLMTextFrame(text="full answer here", response_id="resp_1"))
    await task.queue_frame(LLMFullResponseEndFrame(response_id="resp_1"))
    await asyncio.sleep(0.05)

    await task.queue_frame(InterruptionFrame(response_id="resp_1", audio_played_ms=100))
    await asyncio.sleep(0.05)

    await task.queue_frame(EndFrame())
    await asyncio.sleep(0.05)
    await task.stop()

    snapshot = cs.snapshot()
    assistant = snapshot.items[1]
    # Interruption on its own doesn't trigger truncation — TruncatedFrame must.
    assert assistant.text == "full answer here"
    assert assistant.truncated is False
