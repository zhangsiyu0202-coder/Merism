"""Tests for :class:`~merism.voice.processors.llm.LLMProcessor`."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from merism.voice import (
    EndFrame,
    ErrorFrame,
    Frame,
    FrameDirection,
    FrameProcessor,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    Pipeline,
    PipelineTask,
    TranscriptionFrame,
)
from merism.voice.observer import Observer
from merism.voice.processors.llm import LLMProcessor


class RecordingObserver(Observer):
    def __init__(self) -> None:
        self.seen: list[Frame] = []

    async def on_frame(
        self,
        frame: Frame,
        src: FrameProcessor,
        dst: FrameProcessor | None,
        direction: FrameDirection,
    ) -> None:
        self.seen.append(frame)


class FailingChatClient:
    class chat:  # noqa: N801 - matches OpenAI client shape
        class completions:
            @staticmethod
            def create(*_args, **_kwargs):
                raise RuntimeError("llm backend unavailable")


@pytest.mark.asyncio
async def test_llm_create_failure_emits_error_instead_of_canned_reply() -> None:
    processor = LLMProcessor(system_prompt="You are concise.")
    recorder = RecordingObserver()
    task = PipelineTask(Pipeline([processor]), observer=recorder)

    import merism.voice.processors.llm as llm_module

    original_get_llm = llm_module.get_llm
    llm_module.get_llm = lambda: FailingChatClient()  # type: ignore[assignment]
    try:
        await task.start()
        await task.queue_frame(TranscriptionFrame(text="你好"))
        await asyncio.sleep(0.1)
        await task.queue_frame(EndFrame())
        await asyncio.sleep(0.05)
        await task.stop()
    finally:
        llm_module.get_llm = original_get_llm  # type: ignore[assignment]

    assert any(isinstance(frame, ErrorFrame) for frame in recorder.seen)
    error = next(frame for frame in recorder.seen if isinstance(frame, ErrorFrame))
    assert error.code == "llm_create_failed"
    assert not any(
        isinstance(frame, LLMTextFrame) and frame.text == "嗯，我刚刚没听清，我们继续。"
        for frame in recorder.seen
    )
    assert any(isinstance(frame, LLMFullResponseStartFrame) for frame in recorder.seen)
    assert any(isinstance(frame, LLMFullResponseEndFrame) for frame in recorder.seen)
