"""DashScope Realtime ASR client (``fun-asr-realtime`` / ``qwen3-asr-flash-realtime``).

Protocol modelled on OpenAI's Realtime API:
    - Connect:    ``wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model=<model>``
                  with ``Authorization: Bearer <key>`` + ``OpenAI-Beta: realtime=v1``.
    - Configure:  ``session.update`` with input_audio_format/sample_rate/turn_detection.
    - Stream:     ``input_audio_buffer.append`` (base64 PCM16) events.
    - Receive:    ``conversation.item.input_audio_transcription.text`` (partial)
                  + ``…completed`` (final).
    - Finish:     ``session.finish`` → server sends ``session.finished``.

Events always-on: VAD (server-side), punctuation, emotion. See
``merism.stt.STTEvent`` for the normalised shape exposed to callers.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class STTEvent:
    """Interim or final STT emission. Matches FakeParaformer shape."""

    text: str
    is_final: bool = True
    confidence: float = 1.0
    extra: dict[str, Any] = field(default_factory=dict)


class ParaformerClient:
    """Streaming ASR client talking to DashScope Realtime API.

    The class name is kept (``ParaformerClient``) so the conductor / voice
    consumer don't need to rename imports — the protocol switch is
    internal. Concrete model is read from ``settings.DASHSCOPE_STT_MODEL``
    (defaults to ``fun-asr-realtime``).

    Usage::

        client = ParaformerClient()
        async for event in client.stream_stt(audio_iter):
            if event.is_final:
                handle_final(event.text)
            else:
                handle_partial(event.text)
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        sample_rate: int = 16000,
        language: str = "zh",
        use_server_vad: bool = True,
        url: str | None = None,
    ) -> None:
        self._api_key = api_key or getattr(settings, "DASHSCOPE_ASR_API_KEY", "") or getattr(
            settings, "DASHSCOPE_API_KEY", ""
        )
        self._model = model or getattr(settings, "DASHSCOPE_STT_MODEL", "fun-asr-realtime")
        self._sample_rate = sample_rate
        self._language = language
        self._use_server_vad = use_server_vad
        self._url = url or getattr(
            settings,
            "DASHSCOPE_REALTIME_URL",
            "wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
        )

    @property
    def model(self) -> str:
        return self._model

    async def stream_stt(
        self, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[STTEvent]:
        """Consume PCM16 audio frames; yield STT events as DashScope emits them."""
        if not self._api_key:
            raise RuntimeError(
                "ParaformerClient requires DASHSCOPE_ASR_API_KEY (or DASHSCOPE_API_KEY). "
                "For tests, use merism.testing.fakes.FakeParaformer instead."
            )
        try:
            import websockets
            from websockets.asyncio.client import connect
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "ParaformerClient requires the 'websockets' package. "
                "It is listed in pyproject.toml runtime deps; run `uv sync`."
            ) from exc

        url = f"{self._url}?model={self._model}"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "OpenAI-Beta": "realtime=v1",
        }

        async with connect(url, additional_headers=headers) as ws:
            # Configure the session — input format + VAD mode.
            session_update = {
                "event_id": f"evt_{uuid.uuid4().hex[:12]}",
                "type": "session.update",
                "session": {
                    "modalities": ["text"],
                    "input_audio_format": "pcm",
                    "sample_rate": self._sample_rate,
                    "input_audio_transcription": {"language": self._language},
                    "turn_detection": (
                        {
                            "type": "server_vad",
                            "threshold": 0.0,
                            "silence_duration_ms": 400,
                        }
                        if self._use_server_vad
                        else None
                    ),
                },
            }
            await ws.send(json.dumps(session_update))

            # Background audio pump; main coroutine consumes events.
            sender = asyncio.create_task(
                self._pump_audio(ws, audio_stream, use_server_vad=self._use_server_vad)
            )
            # Watchdog: if the server goes silent for longer than this, bail.
            idle_timeout = 30.0
            finish_sent = False
            try:
                while True:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=idle_timeout)
                    except asyncio.TimeoutError:
                        logger.warning("stt.recv.idle_timeout", extra={"seconds": idle_timeout})
                        break
                    except websockets.exceptions.ConnectionClosed:
                        break
                    if isinstance(raw, bytes):
                        continue
                    event = _parse(raw)
                    if event is None:
                        continue
                    stt = _event_to_stt(event)
                    if stt is not None:
                        yield stt
                    etype = event.get("type")
                    # Once we have a final transcript AND the audio pump has
                    # drained, we can close gracefully.
                    if (
                        etype == "conversation.item.input_audio_transcription.completed"
                        and sender.done()
                        and not finish_sent
                    ):
                        await ws.send(
                            json.dumps(
                                {
                                    "event_id": f"evt_{uuid.uuid4().hex[:12]}",
                                    "type": "session.finish",
                                }
                            )
                        )
                        finish_sent = True
                    if _is_terminal(event):
                        break
            finally:
                sender.cancel()
                try:
                    await sender
                except (asyncio.CancelledError, websockets.exceptions.WebSocketException):
                    pass

    # ── helpers ───────────────────────────────────────────

    async def _pump_audio(
        self,
        ws: Any,
        audio_stream: AsyncIterator[bytes],
        *,
        use_server_vad: bool,
    ) -> None:
        """Stream PCM frames as ``input_audio_buffer.append`` events.

        In manual mode (``use_server_vad=False``) we flush with
        ``input_audio_buffer.commit`` once the stream drains. In server-VAD
        mode we do NOT send ``session.finish`` here — we leave the socket
        open so the server can keep emitting transcription events. The
        outer ``stream_stt`` loop decides when to close.
        """
        try:
            async for chunk in audio_stream:
                if not chunk:
                    continue
                encoded = base64.b64encode(chunk).decode("ascii")
                await ws.send(
                    json.dumps(
                        {
                            "event_id": f"evt_{uuid.uuid4().hex[:12]}",
                            "type": "input_audio_buffer.append",
                            "audio": encoded,
                        }
                    )
                )
            if not use_server_vad:
                # Manual mode: flush the buffer so the server processes
                # what we sent.
                await ws.send(
                    json.dumps(
                        {
                            "event_id": f"evt_{uuid.uuid4().hex[:12]}",
                            "type": "input_audio_buffer.commit",
                        }
                    )
                )
        except Exception as exc:  # pragma: no cover - network
            logger.warning("stt.audio_pipe.failed", extra={"error": str(exc)})


def _parse(raw: str) -> dict[str, Any] | None:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _event_to_stt(event: dict[str, Any]) -> STTEvent | None:
    """Translate one Realtime event to STTEvent, or None to ignore."""
    kind = event.get("type")
    if kind == "conversation.item.input_audio_transcription.text":
        text = (event.get("text") or event.get("stash") or "").strip()
        return STTEvent(text=text, is_final=False) if text else None
    if kind == "conversation.item.input_audio_transcription.completed":
        text = (event.get("transcript") or "").strip()
        return STTEvent(text=text, is_final=True) if text else None
    if kind == "error":
        err = event.get("error") or {}
        raise RuntimeError(
            f"Realtime ASR error: {err.get('code', '?')} — {err.get('message', event)}"
        )
    return None


def _is_terminal(event: dict[str, Any]) -> bool:
    return event.get("type") in ("session.finished", "error")
