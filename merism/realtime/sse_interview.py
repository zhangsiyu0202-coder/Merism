"""Interview session SSE stream.

Produces the wire format that the frontend :class:`SSETestClient` /
participant viewer / researcher observer consumes:

    event: turn
    data: {"role": "agent", "text": "..."}
    id: 1757361922-0

    event: phase_change
    data: {"phase": "active"}
    id: 1757361923-0

Backing store: Redis Streams (one key per session: ``merism:session:<id>:events``).
The moderator runner (``merism.conductor.moderator.stream_turn``) XADDs events
as turns happen; this generator reads them and formats for SSE delivery.

Reconnect is supported: pass ``Last-Event-ID`` header and events emitted
after that ID are replayed.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from django.conf import settings

from merism.models import InterviewSession

logger = logging.getLogger(__name__)

_STREAM_KEY_TMPL = "merism:session:{session_id}:events"
_STREAM_MAXLEN = 5000  # ~60-min voice interview averages ~1500 events
_DEFAULT_POLL_INTERVAL_S = 0.2
_HEARTBEAT_INTERVAL_S = 15


async def iter_session_sse(
    session: InterviewSession,
    *,
    last_event_id: str | None = None,
    poll_interval: float = _DEFAULT_POLL_INTERVAL_S,
) -> AsyncIterator[bytes]:
    """Yield SSE byte chunks for one session.

    Emits past events first (from ``last_event_id`` forward), then tails
    the stream. A ``:keepalive`` comment is sent every 15s to keep
    proxies from closing idle connections.
    """
    redis_client = _redis_client()
    stream_key = _STREAM_KEY_TMPL.format(session_id=session.id)
    cursor = last_event_id or "0-0"

    last_heartbeat = asyncio.get_event_loop().time()

    while True:
        try:
            # XREAD blocks up to 100ms per iteration; caller-configurable via
            # ``poll_interval`` (kept as sleep fallback if XREAD isn't used).
            entries = await redis_client.xread({stream_key: cursor}, count=100, block=200)
        except Exception as exc:  # pragma: no cover
            logger.warning("realtime.sse.xread_failed", extra={"error": str(exc)})
            entries = []

        if entries:
            for _key, messages in entries:
                for message_id, fields in messages:
                    cursor = message_id if isinstance(message_id, str) else message_id.decode()
                    yield _format_event(cursor, fields)
                    last_heartbeat = asyncio.get_event_loop().time()
        else:
            # No new events — send a heartbeat if enough time has elapsed.
            now = asyncio.get_event_loop().time()
            if now - last_heartbeat >= _HEARTBEAT_INTERVAL_S:
                yield b":keepalive\n\n"
                last_heartbeat = now
            await asyncio.sleep(poll_interval)


def _format_event(event_id: str, fields: dict[Any, Any]) -> bytes:
    """Shape one Redis entry into SSE wire bytes.

    Fields schema ``{"event": "turn", "data": "<json string>"}`` — the
    moderator runner stringifies payload JSON before XADD.
    """
    event_name = _decode(fields.get("event", b"message"))
    data = _decode(fields.get("data", b"{}"))
    lines = [f"event: {event_name}", f"data: {data}", f"id: {event_id}", ""]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _decode(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _redis_client() -> Any:
    """Return an async Redis client. Imported lazily so test envs without
    Redis can still import this module."""
    from redis.asyncio import Redis

    return Redis.from_url(settings.REDIS_URL)


async def publish_session_event(
    session_id: str, *, event: str, data: dict[str, Any]
) -> str:
    """XADD a single event to the session stream. Returns the entry id.

    Called by the conductor runner + any task that wants to push a
    progress marker into the live stream.
    """
    redis_client = _redis_client()
    stream_key = _STREAM_KEY_TMPL.format(session_id=session_id)
    entry_id = await redis_client.xadd(
        stream_key,
        {"event": event, "data": json.dumps(data, ensure_ascii=False)},
        maxlen=_STREAM_MAXLEN,
        approximate=True,
    )
    return entry_id.decode() if isinstance(entry_id, bytes) else entry_id
