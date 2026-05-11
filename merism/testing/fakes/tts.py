"""Fake text-to-speech client (CosyVoice / similar).

Emits deterministic audio bytes in response to text chunks. Records every
chunk consumed so tests can assert how the conductor streams text.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field


@dataclass
class _FakeCosyVoiceConfig:
    sample_rate: int = 16000
    voice: str = "merism-test-voice"


class FakeCosyVoice:
    """Pre-canned TTS. Replace ``products.studies.backend.tts.CosyVoiceClient``.

    Example::

        tts = FakeCosyVoice(audio_bytes=b"\\x00\\x01\\x02")
        out = [chunk async for chunk in tts.stream_tts(text_iter)]
        assert b"".join(out) == b"\\x00\\x01\\x02\\x00\\x01\\x02"  # once per text chunk
        assert tts.text_chunks_received == ["hello ", "world"]
    """

    def __init__(self, *, audio_bytes: bytes = b"\x00\x01", voice: str = "merism-test-voice") -> None:
        self._audio_bytes = audio_bytes
        self.config = _FakeCosyVoiceConfig(voice=voice)
        self.text_chunks_received: list[str] = []
        self.call_count: int = 0

    async def stream_tts(self, text_stream: AsyncIterator[str]) -> AsyncIterator[bytes]:
        self.call_count += 1
        async for chunk in text_stream:
            if not chunk:
                continue
            self.text_chunks_received.append(chunk)
            yield self._audio_bytes
