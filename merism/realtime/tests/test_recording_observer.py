"""Unit tests for :class:`~merism.realtime.recording_observer.RecordingObserver`.

Two tiers:

* Pure-python buffer tests (always run) — verify the observer
  accumulates the right bytes from the right frame types.
* Live MinIO upload (``@pytest.mark.merism_storage_live``) — only
  runs when the pytest marker is explicitly enabled AND
  ``OBJECT_STORAGE_ENDPOINT`` is reachable. Validates the full
  ``finalize()`` → boto3 → bucket path.
"""

from __future__ import annotations

import asyncio

import pytest

from merism.realtime.recording_observer import RecordingObserver
from merism.voice import (
    InputAudioRawFrame,
    LLMTextFrame,
    Pipeline,
    PipelineTask,
    TranscriptionFrame,
    TTSAudioRawFrame,
)
from merism.voice.processors import (
    ConversationState,
    STTProcessor,
)


@pytest.mark.asyncio
async def test_recorder_captures_input_audio() -> None:
    """Raw mic frames reach end-of-pipe + land in the mic buffer."""
    recorder = RecordingObserver(session_id="test-sess-mic")
    # Build a minimal pipeline: STT (passes audio through) + conversation state.
    pipeline = Pipeline([STTProcessor(), ConversationState()])
    task = PipelineTask(pipeline, observer=recorder)

    await task.start()
    # 3 chunks of 100 ms of silence at 16 kHz mono PCM16 = 3200 bytes each.
    chunk = b"\x00" * 3200
    for _ in range(3):
        await task.queue_frame(InputAudioRawFrame(audio=chunk, sample_rate=16000))
    await asyncio.sleep(0.1)
    await task.stop()

    assert recorder.mic_bytes == 3 * 3200
    assert recorder.tts_bytes == 0


@pytest.mark.asyncio
async def test_recorder_captures_tts_audio() -> None:
    recorder = RecordingObserver(session_id="test-sess-tts")
    pipeline = Pipeline([ConversationState()])
    task = PipelineTask(pipeline, observer=recorder)

    await task.start()
    chunk = b"\x01" * 4800  # 100 ms @ 24 kHz
    for _ in range(5):
        await task.queue_frame(TTSAudioRawFrame(audio=chunk, sample_rate=24000))
    await asyncio.sleep(0.1)
    await task.stop()

    assert recorder.tts_bytes == 5 * 4800
    assert recorder.mic_bytes == 0


@pytest.mark.asyncio
async def test_recorder_ignores_text_frames() -> None:
    """Non-audio frames don't affect the buffers."""
    recorder = RecordingObserver(session_id="test-sess-text")
    pipeline = Pipeline([ConversationState()])
    task = PipelineTask(pipeline, observer=recorder)

    await task.start()
    await task.queue_frame(TranscriptionFrame(text="hi"))
    await task.queue_frame(LLMTextFrame(text="hello", response_id="r1"))
    await asyncio.sleep(0.05)
    await task.stop()

    assert recorder.mic_bytes == 0
    assert recorder.tts_bytes == 0


def test_finalize_noop_when_no_storage_configured(settings) -> None:
    """If ``OBJECT_STORAGE_ENDPOINT`` is blank, finalize returns empty."""
    settings.OBJECT_STORAGE_ENDPOINT = ""
    settings.OBJECT_STORAGE_BUCKET = "merism-dev"

    recorder = RecordingObserver(session_id="noop-test")
    # Inject some data so we'd attempt upload otherwise.
    recorder._mic_buf.extend(b"\x00" * 1000)
    keys = recorder.finalize()
    assert keys == {}


@pytest.mark.merism_storage_live
def test_finalize_uploads_to_minio(settings) -> None:
    """Live MinIO smoke — requires docker-compose up + MERISM_STORAGE_LIVE=1."""
    import os

    if not os.environ.get("MERISM_STORAGE_LIVE"):
        pytest.skip("set MERISM_STORAGE_LIVE=1 to run live MinIO upload smoke")

    settings.OBJECT_STORAGE_ENDPOINT = os.environ.get(
        "OBJECT_STORAGE_ENDPOINT", "http://localhost:9100"
    )
    settings.OBJECT_STORAGE_BUCKET = os.environ.get("OBJECT_STORAGE_BUCKET", "merism-dev")
    settings.OBJECT_STORAGE_ACCESS_KEY = os.environ.get(
        "OBJECT_STORAGE_ACCESS_KEY", "merism"
    )
    settings.OBJECT_STORAGE_SECRET_KEY = os.environ.get(
        "OBJECT_STORAGE_SECRET_KEY", "merism-dev-password"
    )

    recorder = RecordingObserver(session_id="live-smoke")
    # 1 s of synthetic audio for each side.
    recorder._mic_buf.extend(b"\x00" * 32000)        # 1 s @ 16 kHz PCM16
    recorder._tts_buf.extend(b"\x01" * 48000)        # 1 s @ 24 kHz PCM16

    keys = recorder.finalize()
    assert keys.get("mic") == "live-smoke/mic.pcm"
    assert keys.get("tts") == "live-smoke/tts.pcm"
