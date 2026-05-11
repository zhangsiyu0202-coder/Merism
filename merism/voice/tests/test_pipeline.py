"""Unit tests for the voice pipeline abstractions.

Pure Python — no DashScope / DeepSeek / Redis. Verifies the frame +
processor + observer contracts that underpin STTProcessor / LLMProcessor
/ TTSProcessor (which are separately smoke-tested against live services).
"""

from __future__ import annotations

import asyncio

import pytest

from merism.voice import (
    EndFrame,
    Frame,
    FrameDirection,
    FrameProcessor,
    InterruptionFrame,
    LLMTextFrame,
    MetricsObserver,
    Observer,
    Pipeline,
    PipelineRunner,
    PipelineTask,
    StartFrame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    BotStoppedSpeakingFrame,
    LLMFullResponseStartFrame,
    LLMFullResponseEndFrame,
    TTSAudioRawFrame,
)


class RecorderProcessor(FrameProcessor):
    """Appends every frame it sees to a list."""

    def __init__(self, name: str = "Recorder") -> None:
        super().__init__(name)
        self.seen: list[type] = []

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        self.seen.append(type(frame))
        await self.push_frame(frame, direction)


class RecorderObserver(Observer):
    def __init__(self) -> None:
        self.frames: list[tuple[str, str]] = []

    async def on_frame(
        self,
        frame: Frame,
        src: FrameProcessor,
        dst: FrameProcessor | None,
        direction: FrameDirection,
    ) -> None:
        self.frames.append((src.name, type(frame).__name__))


@pytest.mark.asyncio
async def test_pipeline_passes_frames_in_order() -> None:
    p1 = RecorderProcessor("A")
    p2 = RecorderProcessor("B")
    p3 = RecorderProcessor("C")
    pipeline = Pipeline([p1, p2, p3])
    task = PipelineTask(pipeline)

    await task.start()
    await task.queue_frames(
        [TranscriptionFrame(text="hi"), LLMTextFrame(text="hello")]
    )

    # Drain — give the event loop enough ticks to process
    for _ in range(10):
        await asyncio.sleep(0.01)

    await task.queue_frame(EndFrame())
    for _ in range(10):
        await asyncio.sleep(0.01)
    await task.stop()

    # Every processor sees StartFrame → TranscriptionFrame → LLMTextFrame → EndFrame
    for p in (p1, p2, p3):
        seq = [t.__name__ for t in p.seen]
        assert "StartFrame" in seq
        assert seq.index("TranscriptionFrame") < seq.index("LLMTextFrame")


@pytest.mark.asyncio
async def test_interruption_drops_queued_data_frames() -> None:
    """An InterruptionFrame MUST clear the data queue downstream."""

    class SlowProcessor(FrameProcessor):
        """Simulates a backlog by delaying each data frame 20 ms."""

        def __init__(self) -> None:
            super().__init__("Slow")
            self.data_processed: list[type] = []

        async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
            # Only track DataFrame types that would be dropped.
            if isinstance(frame, LLMTextFrame):
                await asyncio.sleep(0.02)
                self.data_processed.append(type(frame))
            await self.push_frame(frame, direction)

    slow = SlowProcessor()
    sink = RecorderProcessor("Sink")
    pipeline = Pipeline([slow, sink])
    task = PipelineTask(pipeline)

    await task.start()
    # Queue up 10 data frames, then immediately interrupt.
    for i in range(10):
        await task.queue_frame(LLMTextFrame(text=f"chunk-{i}"))
    await task.queue_frame(InterruptionFrame())

    await asyncio.sleep(0.2)          # let things settle
    await task.queue_frame(EndFrame())
    await asyncio.sleep(0.1)
    await task.stop()

    # After the interruption, the slow processor should NOT have
    # processed all 10 chunks — the queue was cleared.
    assert len(slow.data_processed) < 10, (
        f"Interruption failed to drop data queue: "
        f"{len(slow.data_processed)} of 10 still processed"
    )


@pytest.mark.asyncio
async def test_observer_sees_every_push() -> None:
    p1 = RecorderProcessor("A")
    p2 = RecorderProcessor("B")
    pipeline = Pipeline([p1, p2])
    observer = RecorderObserver()
    task = PipelineTask(pipeline, observer=observer)

    await task.start()
    await task.queue_frame(TranscriptionFrame(text="hi"))
    await task.queue_frame(EndFrame())
    await asyncio.sleep(0.05)
    await task.stop()

    # Observer sees the push from every processor + the final push-off-pipe.
    assert any(name == "A" and f == "TranscriptionFrame" for name, f in observer.frames)
    assert any(name == "B" and f == "TranscriptionFrame" for name, f in observer.frames)


@pytest.mark.asyncio
async def test_metrics_observer_computes_stt_latency() -> None:
    """UserStoppedSpeakingFrame → TranscriptionFrame delta = stt_latency."""
    pipeline = Pipeline([RecorderProcessor("A")])
    metrics = MetricsObserver()
    task = PipelineTask(pipeline, observer=metrics)

    await task.start()
    await task.queue_frame(UserStoppedSpeakingFrame())
    await asyncio.sleep(0.05)         # inject 50 ms of synthetic STT latency
    await task.queue_frame(TranscriptionFrame(text="hello"))
    await asyncio.sleep(0.05)

    summary = metrics.summary()
    assert "stt_latency" in summary
    stt = summary["stt_latency"]
    assert stt["count"] == 1
    # At least the synthetic 50 ms, at most a reasonable ceiling.
    assert 30.0 < stt["mean"] < 500.0, f"stt_latency {stt['mean']} outside expected range"

    await task.queue_frame(EndFrame())
    await asyncio.sleep(0.05)
    await task.stop()


@pytest.mark.asyncio
async def test_pipeline_runner_lifecycle() -> None:
    pipeline = Pipeline([RecorderProcessor("X")])
    task = PipelineTask(pipeline)
    runner = PipelineRunner(handle_sigint=False)

    async def run_and_close():
        await task.queue_frame(EndFrame())
        await task.cancel()

    await asyncio.gather(runner.run(task), run_and_close())
