"""RecordingObserver — session audio archive.

Listens for two frame types on the pipeline:
    - :class:`InputAudioRawFrame`   (participant mic, 16 kHz PCM16 mono)
    - :class:`TTSAudioRawFrame`     (moderator voice, 24 kHz PCM16 mono)

Accumulates both in-process. On :meth:`finalize` (invoked by the
consumer on disconnect) uploads the two PCM blobs to object storage
under the session-scoped prefix:

    {session_id}/mic.pcm
    {session_id}/tts.pcm

Returns the S3 keys so the consumer can persist them on
``InterviewSession.audio_s3_key`` / ``.video_s3_key``. Audio remains
raw PCM for cheapest write-path; transcoding to OGG/MP3 for
playback-in-browser is a batch job downstream.

Why raw PCM, not WAV? WAV needs a header with known length upfront,
which we don't have until the session ends. Post-processing wraps the
PCM in a WAV header in a single pass.

Memory budget: 16 kHz mono PCM16 is 32 KB/s → ~1.9 MB/min. A 60-min
interview is ~115 MB in RAM. Acceptable for now; if we hit scale we
can stream-write to disk in chunks.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.conf import settings

from merism.voice import (
    Frame,
    InputAudioRawFrame,
    Observer,
    TTSAudioRawFrame,
)

if TYPE_CHECKING:
    from merism.voice import FrameDirection, FrameProcessor

logger = logging.getLogger(__name__)


class RecordingObserver(Observer):
    """Buffers mic + TTS audio; uploads to S3 on finalize."""

    def __init__(self, session_id: str) -> None:
        self._session_id = session_id
        self._mic_buf = bytearray()
        self._tts_buf = bytearray()

    async def on_frame(
        self,
        frame: Frame,
        src: "FrameProcessor",
        dst: "FrameProcessor | None",
        direction: "FrameDirection",
    ) -> None:
        # Only capture at end-of-pipe for natural dedup.
        if dst is not None:
            return

        if isinstance(frame, InputAudioRawFrame) and frame.audio:
            self._mic_buf.extend(frame.audio)
            return

        if isinstance(frame, TTSAudioRawFrame) and frame.audio:
            self._tts_buf.extend(frame.audio)
            return

    @property
    def mic_bytes(self) -> int:
        return len(self._mic_buf)

    @property
    def tts_bytes(self) -> int:
        return len(self._tts_buf)

    def finalize(self) -> dict[str, str]:
        """Upload the buffered audio. Returns the S3 keys written.

        Called synchronously on session disconnect. No-op if either
        buffer is empty OR no storage endpoint is configured.
        """
        result: dict[str, str] = {}
        endpoint = getattr(settings, "OBJECT_STORAGE_ENDPOINT", "")
        bucket = getattr(settings, "OBJECT_STORAGE_BUCKET", "")
        if not endpoint or not bucket:
            logger.info(
                "voice.recording.storage_not_configured",
                extra={"session_id": self._session_id},
            )
            return result

        try:
            import boto3
            from botocore.client import Config
        except ImportError:  # pragma: no cover
            logger.warning("voice.recording.boto3_missing")
            return result

        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=getattr(settings, "OBJECT_STORAGE_ACCESS_KEY", "") or None,
            aws_secret_access_key=getattr(settings, "OBJECT_STORAGE_SECRET_KEY", "") or None,
            region_name=getattr(settings, "OBJECT_STORAGE_REGION", "us-east-1"),
            config=Config(signature_version="s3v4"),
        )

        # Ensure the bucket exists (MinIO dev doesn't auto-create).
        try:
            client.head_bucket(Bucket=bucket)
        except Exception:
            try:
                client.create_bucket(Bucket=bucket)
            except Exception as exc:
                logger.warning(
                    "voice.recording.create_bucket_failed",
                    extra={"bucket": bucket, "error": str(exc)},
                )
                return result

        if self._mic_buf:
            mic_key = f"{self._session_id}/mic.pcm"
            try:
                client.put_object(
                    Bucket=bucket,
                    Key=mic_key,
                    Body=bytes(self._mic_buf),
                    ContentType="audio/pcm",
                    Metadata={
                        "session_id": self._session_id,
                        "sample_rate": "16000",
                        "channels": "1",
                        "bits": "16",
                    },
                )
                result["mic"] = mic_key
                logger.info(
                    "voice.recording.uploaded",
                    extra={"key": mic_key, "bytes": len(self._mic_buf)},
                )
            except Exception as exc:
                logger.warning(
                    "voice.recording.mic_upload_failed", extra={"error": str(exc)}
                )

        if self._tts_buf:
            tts_key = f"{self._session_id}/tts.pcm"
            try:
                client.put_object(
                    Bucket=bucket,
                    Key=tts_key,
                    Body=bytes(self._tts_buf),
                    ContentType="audio/pcm",
                    Metadata={
                        "session_id": self._session_id,
                        "sample_rate": "24000",
                        "channels": "1",
                        "bits": "16",
                    },
                )
                result["tts"] = tts_key
                logger.info(
                    "voice.recording.uploaded",
                    extra={"key": tts_key, "bytes": len(self._tts_buf)},
                )
            except Exception as exc:
                logger.warning(
                    "voice.recording.tts_upload_failed", extra={"error": str(exc)}
                )

        return result
