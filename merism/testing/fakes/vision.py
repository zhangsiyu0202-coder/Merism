"""Fake vision client for video-interview frame description.

Swaps for Merism's ``describe_frame`` / OpenAI-compatible vision calls.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _FakeVisionCall:
    frame_bytes_len: int
    prompt: str
    extra: dict[str, Any] = field(default_factory=dict)


class FakeVisionClient:
    """Returns pre-canned frame descriptions in order.

    Example::

        vision = FakeVisionClient(descriptions=["smiling", "looking away"])
        desc1 = vision.describe_frame(frame_bytes=b"jpeg...", prompt="What do you see?")
        desc2 = vision.describe_frame(frame_bytes=b"jpeg...", prompt="What do you see?")
        assert [desc1, desc2] == ["smiling", "looking away"]
        assert len(vision.calls) == 2
    """

    def __init__(
        self,
        *,
        descriptions: Iterable[str] = (),
        default: str = "",
    ) -> None:
        self._queue: list[str] = list(descriptions)
        self._default = default
        self.calls: list[_FakeVisionCall] = []

    def describe_frame(self, *, frame_bytes: bytes, prompt: str = "", **extra: Any) -> str:
        self.calls.append(
            _FakeVisionCall(frame_bytes_len=len(frame_bytes or b""), prompt=prompt, extra=extra)
        )
        if not frame_bytes:
            return ""
        if self._queue:
            return self._queue.pop(0)
        return self._default
