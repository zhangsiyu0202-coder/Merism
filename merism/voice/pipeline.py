"""Pipeline orchestration.

Directly modeled on pipecat v1 (BSD-2): a :class:`Pipeline` is an
ordered list of :class:`FrameProcessor` s. Frames flow downstream by
default; any processor may ``push_frame(frame, UPSTREAM)`` to feedback
(e.g. STT → transport saying "reset my audio buffer").

Two queues per processor:
- ``_system_q`` for :class:`~merism.voice.frames.SystemFrame` (high-priority,
  ordered among themselves, survive interruption).
- ``_data_q`` for :class:`~merism.voice.frames.DataFrame` and
  :class:`~merism.voice.frames.ControlFrame` (dropped on interruption).

The processor processes a SystemFrame ASAP; DataFrames process only
when no system backlog remains.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import signal
from typing import TYPE_CHECKING

from .frames import (
    CancelFrame,
    ControlFrame,
    DataFrame,
    EndFrame,
    ErrorFrame,
    Frame,
    InterruptionFrame,
    StartFrame,
    SystemFrame,
)

if TYPE_CHECKING:
    from .observer import Observer

logger = logging.getLogger(__name__)


class FrameDirection(enum.Enum):
    DOWNSTREAM = "downstream"
    UPSTREAM = "upstream"


class FrameProcessor:
    """Base class for everything on the pipeline.

    Lifecycle:
        __init__         — instance creation, no I/O
        start()          — allocate resources (network connections, etc.)
        process_frame()  — handle one frame, push zero or more onward
        stop()           — release resources

    Subclasses override :meth:`process_frame` AND must
    ``await self.push_frame(frame, direction)`` at the end (usually)
    so the next processor in the chain receives the frame.

    To drop a frame, simply omit the push.
    """

    def __init__(self, name: str | None = None) -> None:
        self._name = name or type(self).__name__
        self._next: FrameProcessor | None = None       # downstream
        self._prev: FrameProcessor | None = None       # upstream
        self._observer: Observer | None = None
        self._system_q: asyncio.Queue[tuple[Frame, FrameDirection]] = asyncio.Queue()
        self._data_q: asyncio.Queue[tuple[Frame, FrameDirection]] = asyncio.Queue()
        self._started = False
        self._stopped = False
        self._workers: list[asyncio.Task[None]] = []

    @property
    def name(self) -> str:
        return self._name

    # ── linking ──────────────────────────────────────────

    def link(self, next_processor: FrameProcessor) -> FrameProcessor:
        """Connect this processor to the next one in the chain."""
        self._next = next_processor
        next_processor._prev = self
        return next_processor

    def set_observer(self, observer: Observer | None) -> None:
        self._observer = observer

    # ── lifecycle ────────────────────────────────────────

    async def start(self) -> None:
        """Allocate resources. Override to open sockets etc."""
        if self._started:
            return
        self._started = True
        # Two workers: system-frame draining (high priority) + data.
        self._workers = [
            asyncio.create_task(self._system_loop(), name=f"{self._name}.sys"),
            asyncio.create_task(self._data_loop(), name=f"{self._name}.data"),
        ]

    async def stop(self) -> None:
        """Release resources. Override to close sockets etc."""
        if self._stopped:
            return
        self._stopped = True
        for t in self._workers:
            t.cancel()
        for t in self._workers:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass

    # ── public push ─────────────────────────────────────

    async def push_frame(
        self,
        frame: Frame,
        direction: FrameDirection = FrameDirection.DOWNSTREAM,
    ) -> None:
        """Send a frame to the next processor (or prev, for UPSTREAM)."""
        target = self._next if direction == FrameDirection.DOWNSTREAM else self._prev
        if target is None:
            # End of the pipe in that direction — the observer still sees it.
            if self._observer is not None:
                await self._observer.on_frame(frame, self, None, direction)
            return

        if self._observer is not None:
            await self._observer.on_frame(frame, self, target, direction)

        if isinstance(frame, SystemFrame):
            await target._system_q.put((frame, direction))
        else:
            await target._data_q.put((frame, direction))

    # ── override points ─────────────────────────────────

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Handle ``frame`` then (usually) ``push_frame`` it onward.

        Default behaviour: pass through unchanged. Override in subclasses.
        """
        await self.push_frame(frame, direction)

    # ── worker loops (private) ───────────────────────────

    async def _system_loop(self) -> None:
        while True:
            frame, direction = await self._system_q.get()
            try:
                await self._dispatch(frame, direction, is_system=True)
            except Exception as exc:
                logger.exception("pipeline.system_processor_error", extra={"processor": self._name})
                await self.push_frame(
                    ErrorFrame(code="processor_error", message=str(exc)), direction
                )

    async def _data_loop(self) -> None:
        while True:
            # Prefer draining system queue first — but the dedicated
            # system worker already does that. Here we just process data.
            frame, direction = await self._data_q.get()
            try:
                await self._dispatch(frame, direction, is_system=False)
            except Exception as exc:
                logger.exception("pipeline.data_processor_error", extra={"processor": self._name})
                await self.push_frame(
                    ErrorFrame(code="processor_error", message=str(exc)), direction
                )

    async def _dispatch(
        self,
        frame: Frame,
        direction: FrameDirection,
        is_system: bool,
    ) -> None:
        # Interruption drops the data queue (but keeps system frames).
        if isinstance(frame, InterruptionFrame) and is_system:
            while not self._data_q.empty():
                try:
                    self._data_q.get_nowait()
                except asyncio.QueueEmpty:
                    break
        await self.process_frame(frame, direction)


# ── pipeline ─────────────────────────────────────────────


class Pipeline(FrameProcessor):
    """A linear chain of processors.

    The Pipeline *is* a FrameProcessor so it can be nested. Its
    ``process_frame`` just pushes onto the first child's queue.
    """

    def __init__(self, processors: list[FrameProcessor], name: str = "Pipeline") -> None:
        super().__init__(name)
        assert processors, "Pipeline requires at least one processor"
        self._processors = processors
        # Link them in order.
        for a, b in zip(processors, processors[1:], strict=False):
            a.link(b)
        self._first = processors[0]
        self._last = processors[-1]

    async def start(self) -> None:
        await super().start()
        for p in self._processors:
            await p.start()

    async def stop(self) -> None:
        for p in reversed(self._processors):
            await p.stop()
        await super().stop()

    async def push_frame(
        self,
        frame: Frame,
        direction: FrameDirection = FrameDirection.DOWNSTREAM,
    ) -> None:
        """Inject a frame at the top of the pipeline."""
        if isinstance(frame, SystemFrame):
            await self._first._system_q.put((frame, direction))
        else:
            await self._first._data_q.put((frame, direction))

    def set_observer(self, observer: Observer | None) -> None:
        for p in self._processors:
            p.set_observer(observer)


# ── task + runner ────────────────────────────────────────


class PipelineTask:
    """One running invocation of a pipeline.

    Wraps lifecycle + observer binding + a future that resolves when the
    pipeline drains an ``EndFrame``.
    """

    def __init__(
        self,
        pipeline: Pipeline,
        *,
        observer: Observer | None = None,
        sample_rate: int = 16000,
    ) -> None:
        self._pipeline = pipeline
        self._observer = observer
        self._sample_rate = sample_rate
        self._done: asyncio.Future[None] | None = None

    @property
    def pipeline(self) -> Pipeline:
        return self._pipeline

    async def queue_frame(
        self,
        frame: Frame,
        direction: FrameDirection = FrameDirection.DOWNSTREAM,
    ) -> None:
        await self._pipeline.push_frame(frame, direction)

    async def queue_frames(self, frames: list[Frame]) -> None:
        for f in frames:
            await self.queue_frame(f)

    async def start(self) -> None:
        if self._observer is not None:
            self._pipeline.set_observer(self._observer)
        await self._pipeline.start()
        self._done = asyncio.get_running_loop().create_future()
        await self.queue_frame(StartFrame(sample_rate=self._sample_rate))

    async def cancel(self) -> None:
        await self.queue_frame(CancelFrame())
        if self._done is not None and not self._done.done():
            self._done.set_result(None)

    async def wait(self) -> None:
        if self._done is None:
            return
        await self._done

    async def stop(self) -> None:
        await self._pipeline.stop()
        if self._done is not None and not self._done.done():
            self._done.set_result(None)


class PipelineRunner:
    """Runs a :class:`PipelineTask` to completion.

    Responsible for:
    - start / stop / wait orchestration
    - SIGINT / SIGTERM graceful shutdown (optional)
    - resource cleanup on exception
    """

    def __init__(self, *, handle_sigint: bool = False) -> None:
        self._handle_sigint = handle_sigint
        self._task: PipelineTask | None = None
        self._cancelled = False

    async def run(self, task: PipelineTask) -> None:
        self._task = task
        if self._handle_sigint:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, lambda: asyncio.create_task(self._on_signal()))
                except (NotImplementedError, RuntimeError):
                    # Windows / non-main thread — signal handlers unavailable.
                    pass

        await task.start()
        try:
            await task.wait()
        except asyncio.CancelledError:
            self._cancelled = True
            raise
        finally:
            await task.stop()

    async def _on_signal(self) -> None:
        if self._task is not None:
            await self._task.cancel()
