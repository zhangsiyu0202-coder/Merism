"""DashScope Realtime TTS client (``qwen3-tts-instruct-flash-realtime``).

Protocol (per live smoke against ``wss://dashscope.aliyuncs.com/api-ws/v1/realtime``):

    client → server
        session.update
        input_text_buffer.append  (one per text chunk)
        input_text_buffer.commit  (force synthesis)
        session.finish            (only AFTER response.audio.done)

    server → client
        session.created
        session.updated
        input_text_buffer.committed
        response.created
        response.output_item.added
        response.content_part.added
        response.audio.delta × N   ← base64-PCM audio bytes
        response.audio.done
        response.content_part.done
        response.output_item.done
        response.done
        session.finished
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class TTSConfig:
    voice: str = "Cherry"
    sample_rate: int = 24000
    response_format: str = "pcm"   # only format supported by the realtime TTS family
    language_type: str = "Chinese"


class CosyVoiceClient:
    """Streaming TTS client over the DashScope Realtime API.

    Manual-commit mode (``mode="commit"``): we decide when to synthesise
    via :data:`input_text_buffer.commit`. This yields the lowest latency
    and matches the conductor loop's stream-then-flush pattern.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        voice: str = "Cherry",
        language_type: str = "Chinese",
        url: str | None = None,
    ) -> None:
        self._api_key = api_key or getattr(settings, "DASHSCOPE_TTS_API_KEY", "") or getattr(
            settings, "DASHSCOPE_API_KEY", ""
        )
        self._model = model or getattr(
            settings, "DASHSCOPE_TTS_MODEL", "qwen3-tts-instruct-flash-realtime"
        )
        self.config = TTSConfig(voice=voice, language_type=language_type)
        self._url = url or getattr(
            settings,
            "DASHSCOPE_REALTIME_URL",
            "wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
        )

    async def stream_tts(self, text_stream: AsyncIterator[str]) -> AsyncIterator[bytes]:
        if not self._api_key:
            raise RuntimeError(
                "CosyVoiceClient requires DASHSCOPE_TTS_API_KEY (or DASHSCOPE_API_KEY)."
            )
        try:
            import websockets
            from websockets.asyncio.client import connect
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "CosyVoiceClient requires the 'websockets' package. Run `uv sync`."
            ) from exc

        url = f"{self._url}?model={self._model}"
        headers = {"Authorization": f"Bearer {self._api_key}"}

        async with connect(url, additional_headers=headers) as ws:
            await ws.send(
                json.dumps(
                    {
                        "event_id": _evt_id(),
                        "type": "session.update",
                        "session": {
                            "voice": self.config.voice,
                            "mode": "commit",
                            "language_type": self.config.language_type,
                            "response_format": self.config.response_format,
                            "sample_rate": self.config.sample_rate,
                        },
                    }
                )
            )

            sender = asyncio.create_task(self._pump_text(ws, text_stream))
            finish_sent = False
            # Watchdog: if we stop seeing events for this long, bail.
            # Prevents the 300 s server-side idle timeout from hanging callers.
            idle_timeout = 30.0
            try:
                while True:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=idle_timeout)
                    except asyncio.TimeoutError:
                        logger.warning("tts.recv.idle_timeout", extra={"seconds": idle_timeout})
                        break
                    except websockets.exceptions.ConnectionClosed:
                        break
                    if isinstance(raw, bytes):
                        if raw:
                            yield raw
                        continue
                    event = _parse(raw)
                    if event is None:
                        continue
                    audio = _extract_audio(event)
                    if audio is not None:
                        yield audio
                    etype = event.get("type")
                    if etype == "response.audio.done" and not finish_sent:
                        await ws.send(
                            json.dumps({"event_id": _evt_id(), "type": "session.finish"})
                        )
                        finish_sent = True
                    if etype in ("session.finished", "error"):
                        break
            finally:
                sender.cancel()
                try:
                    await sender
                except (asyncio.CancelledError, websockets.exceptions.WebSocketException):
                    pass

    async def _pump_text(self, ws: Any, text_stream: AsyncIterator[str]) -> None:
        """Feed text chunks then commit once drained.

        Because we use ``mode="commit"``, ``input_text_buffer.commit``
        is the signal that kicks synthesis. Upstream may feed chunks as
        LLM tokens stream in, and we commit after the stream drains.
        """
        try:
            async for chunk in text_stream:
                if not chunk:
                    continue
                await ws.send(
                    json.dumps(
                        {
                            "event_id": _evt_id(),
                            "type": "input_text_buffer.append",
                            "text": chunk,
                        }
                    )
                )
            # Commit after the text stream drains.
            await ws.send(
                json.dumps({"event_id": _evt_id(), "type": "input_text_buffer.commit"})
            )
        except Exception as exc:  # pragma: no cover - network
            logger.warning("tts.text_pipe.failed", extra={"error": str(exc)})


def _parse(raw: str) -> dict[str, Any] | None:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _extract_audio(event: dict[str, Any]) -> bytes | None:
    if event.get("type") == "response.audio.delta":
        delta = event.get("delta") or event.get("audio")
        if delta:
            try:
                return base64.b64decode(delta)
            except (ValueError, TypeError):
                return None
    if event.get("type") == "error":
        err = event.get("error") or {}
        raise RuntimeError(
            f"Realtime TTS error: {err.get('code', '?')} — {err.get('message', event)}"
        )
    return None


def _evt_id() -> str:
    return f"evt_{uuid.uuid4().hex[:12]}"
