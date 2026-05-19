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
import os
import json
import logging
import uuid
import unicodedata
from contextlib import asynccontextmanager
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


_FILLER_TRANSCRIPTS = {
    "嗯",
    "啊",
    "呃",
    "额",
    "哦",
    "唔",
    "诶",
    "欸",
}


def should_ignore_transcript(text: str) -> bool:
    """Return ``True`` for standalone filler/noise transcripts.

    The realtime ASR sometimes emits single-character hesitation tokens
    like ``嗯`` or ``啊`` as a separate final transcript when the user
    pauses or the turn closes on trailing silence. Those are low-value
    in interview transcripts, so we suppress them here rather than
    showing them as standalone messages.
    """

    cleaned = "".join(
        ch for ch in text.strip() if unicodedata.category(ch)[0] not in {"P", "S", "Z"}
    )
    if not cleaned:
        return True
    if cleaned in _FILLER_TRANSCRIPTS:
        return True
    if len(cleaned) <= 2 and len(set(cleaned)) == 1 and cleaned[0] in _FILLER_TRANSCRIPTS:
        return True
    return False


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
        try:
            import websockets
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "ParaformerClient requires the 'websockets' package. "
                "It is listed in pyproject.toml runtime deps; run `uv sync`."
            ) from exc

        async with self._open_session() as ws:
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

    async def warmup(self, timeout_s: float = 3.0) -> None:
        """Open and configure a Realtime session so the first turn is warm."""
        try:
            async with self._open_session() as ws:
                try:
                    async with asyncio.timeout(timeout_s):
                        while True:
                            raw = await ws.recv()
                            if isinstance(raw, bytes):
                                continue
                            event = _parse(raw)
                            if event is None:
                                continue
                            if event.get("type") in {"session.created", "session.updated"}:
                                return
                            if event.get("type") == "error":
                                _event_to_stt(event)
                except TimeoutError:
                    logger.info("stt.warmup.timeout", extra={"seconds": timeout_s})
        except Exception as exc:
            logger.warning("stt.warmup.failed", extra={"error": str(exc)})

    def _session_update(self) -> dict[str, Any]:
        vad_threshold = float(
            getattr(settings, "DASHSCOPE_STT_VAD_THRESHOLD", os.environ.get("DASHSCOPE_STT_VAD_THRESHOLD", "0.5"))
        )
        vad_silence_ms = int(
            getattr(settings, "DASHSCOPE_STT_VAD_SILENCE_MS", os.environ.get("DASHSCOPE_STT_VAD_SILENCE_MS", "600"))
        )
        return {
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
                        "threshold": vad_threshold,
                        "silence_duration_ms": vad_silence_ms,
                    }
                    if self._use_server_vad
                    else None
                ),
            },
        }

    @asynccontextmanager
    async def _open_session(self) -> AsyncIterator[Any]:
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

        ws = await connect(url, additional_headers=headers)
        try:
            await ws.send(json.dumps(self._session_update()))
            yield ws
        finally:
            try:
                await ws.close()
            except Exception:  # pragma: no cover - best effort cleanup
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
