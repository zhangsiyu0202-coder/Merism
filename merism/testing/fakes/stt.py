"""Fake speech-to-text client (Paraformer / similar).

Yields pre-canned transcripts in response to any audio input. Records the
number of calls and the byte count processed so tests can assert throughput.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeSTTEvent:
    """Mirrors real STT adapters' event shape."""

    text: str
    is_final: bool = True
    confidence: float = 1.0
    extra: dict[str, Any] = field(default_factory=dict)


class FakeParaformer:
    """Pre-canned STT. Replace ``products.studies.backend.stt.ParaformerClient``.

    Example::

        stt = FakeParaformer(transcripts=["hello", "how are you"])
        events = [e async for e in stt.stream_stt(audio_iter)]
        assert [e.text for e in events] == ["hello", "how are you"]
    """

    def __init__(
        self,
        *,
        transcripts: Iterable[str] = (),
        raise_on_next: Exception | None = None,
    ) -> None:
        self._transcripts: list[str] = list(transcripts)
        self._raise_on_next = raise_on_next
        self.call_count: int = 0
        self.bytes_processed: int = 0

    def push(self, text: str) -> None:
        self._transcripts.append(text)

    def raise_on_next(self, exc: Exception) -> None:
        self._raise_on_next = exc

    async def stream_stt(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[FakeSTTEvent]:
        self.call_count += 1
        async for chunk in audio_stream:
            self.bytes_processed += len(chunk)
        if self._raise_on_next is not None:
            exc = self._raise_on_next
            self._raise_on_next = None
            raise exc
        for text in self._transcripts:
            yield FakeSTTEvent(text=text)
