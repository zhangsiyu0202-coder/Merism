"""SSE test client.

Collects events from an SSE async generator (the shape Merism's interview
streaming produces) and lets tests assert on the ordered sequence.

The client is deliberately transport-agnostic — it consumes any ``AsyncIterator``
yielding ``bytes`` in the SSE wire format (``event: X\\ndata: Y\\n\\n``). You can
plug in either a real interview stream generator or a custom byte iterator.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from typing import Any


@dataclass
class SSEEvent:
    """A single parsed SSE event."""

    event: str  # e.g., "turn", "phase_change", "error"
    data: str
    id: str | None = None
    retry: int | None = None


class SSETestClient:
    """Consume SSE bytes from an async generator and record events.

    Example::

        async def produce():
            yield b"event: turn\\ndata: hello\\nid: 1\\n\\n"
            yield b"event: phase_change\\ndata: active\\nid: 2\\n\\n"

        client = SSETestClient()
        await client.collect_from(produce())
        assert [e.event for e in client.events] == ["turn", "phase_change"]
    """

    def __init__(self) -> None:
        self.events: list[SSEEvent] = []
        self._buffer = ""

    # ─── Collection ─────────────────────────────────────────────

    async def collect_from(self, source: AsyncIterator[bytes], *, max_events: int | None = None) -> None:
        """Consume ``source`` until exhaustion or ``max_events`` reached."""
        async for chunk in source:
            self._feed(chunk.decode("utf-8"))
            if max_events is not None and len(self.events) >= max_events:
                return

    def collect_from_sync(self, source: Iterable[bytes], *, max_events: int | None = None) -> None:
        """Sync version — consume ``source`` from a regular iterator."""
        for chunk in source:
            self._feed(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk)
            if max_events is not None and len(self.events) >= max_events:
                return

    def collect_within(self, source: AsyncIterator[bytes], timeout: float = 1.0) -> None:
        """Run ``collect_from`` to completion with a timeout (seconds)."""
        asyncio.run(asyncio.wait_for(self.collect_from(source), timeout=timeout))

    # ─── Parsing ────────────────────────────────────────────────

    def _feed(self, text: str) -> None:
        self._buffer += text
        while "\n\n" in self._buffer:
            raw_event, self._buffer = self._buffer.split("\n\n", 1)
            event = _parse_sse_block(raw_event)
            if event is not None:
                self.events.append(event)

    # ─── Query helpers ──────────────────────────────────────────

    def event_names(self) -> list[str]:
        return [e.event for e in self.events]

    def filter(self, event: str) -> list[SSEEvent]:
        return [e for e in self.events if e.event == event]

    def last_id(self) -> str | None:
        for e in reversed(self.events):
            if e.id:
                return e.id
        return None

    def as_dicts(self) -> list[dict[str, Any]]:
        return [
            {"event": e.event, "data": e.data, "id": e.id, "retry": e.retry}
            for e in self.events
        ]


def _parse_sse_block(raw: str) -> SSEEvent | None:
    """Parse one SSE ``event: ...\\ndata: ...`` block.

    Tolerates: multi-line data fields (joined with ``\\n``), missing event name
    (defaults to ``"message"`` per spec), and comment lines starting with ``:``.
    """
    event_name = "message"
    data_lines: list[str] = []
    event_id: str | None = None
    retry: int | None = None

    for line in raw.splitlines():
        if not line or line.startswith(":"):
            continue
        if ":" in line:
            field, _, value = line.partition(":")
            value = value.lstrip(" ")
        else:
            field, value = line, ""

        if field == "event":
            event_name = value
        elif field == "data":
            data_lines.append(value)
        elif field == "id":
            event_id = value
        elif field == "retry":
            try:
                retry = int(value)
            except ValueError:
                pass

    if not data_lines and event_name == "message":
        return None  # Empty block — ignore.

    return SSEEvent(event=event_name, data="\n".join(data_lines), id=event_id, retry=retry)
