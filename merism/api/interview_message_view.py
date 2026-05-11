"""Text-mode interview turn endpoint.

``POST /api/sessions/<id>/message/`` with ``{ "message": "<text>" }``
yields an SSE stream of ``delta`` events (incremental model text) and a
final ``done`` event carrying the structured decision. Under the hood
this invokes :func:`merism.conductor.moderator.stream_turn` — the same
code path used by the voice pipeline — so text and voice modes share
the authoritative turn logic.

This endpoint is mounted **outside** the DRF router so the SSE framing
is simple and there is no serializer/throttle round-trip per chunk.

Authentication: none. Participants are anonymous, identified by the
browser cookie set by ``/i/<slug>/``. The cookie is checked against the
Participation bound to the requested session.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Iterator

from asgiref.sync import sync_to_async
from django.http import HttpRequest, JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from merism.conductor.moderator import stream_turn
from merism.models import InterviewSession
from merism.observability import bind_trace
from merism.participant.views import COOKIE_NAME

logger = logging.getLogger(__name__)


def _sse(event: str, data: dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode(
        "utf-8"
    )


def _authorize(request: HttpRequest, session: InterviewSession) -> bool:
    """Cookie browser_token must match session.participation.browser_token."""
    participation = session.participation
    if participation is None:
        return False
    raw = request.COOKIES.get(COOKIE_NAME)
    if not raw:
        return False
    try:
        return uuid.UUID(raw) == participation.browser_token
    except (ValueError, TypeError):
        return False


def _stream_bytes(session_id: str, message: str) -> Iterator[bytes]:
    """Drive the async ``stream_turn`` generator from a sync Django view.

    The runtime layout:

    - One fresh event loop per request (simple, no cross-request state).
    - An asyncio.Queue shuttles each text delta from the moderator
      coroutine to the sync caller, which immediately yields SSE bytes.
    - A ``__end__`` sentinel cleanly terminates the loop.
    """
    queue: asyncio.Queue = asyncio.Queue()

    async def _producer() -> None:
        try:
            session = await sync_to_async(
                lambda: InterviewSession.objects.select_related(
                    "study", "guide", "participation"
                ).get(id=session_id)
            )()
            async for delta in stream_turn(session, participant_message=message):
                await queue.put(("delta", delta))
            await queue.put(("done", session_id))
        except Exception as exc:  # pragma: no cover - safety net
            logger.exception("text_message.stream_failed")
            await queue.put(("error", str(exc)))
        finally:
            await queue.put(("__end__", None))

    loop = asyncio.new_event_loop()
    try:
        producer_task = loop.create_task(_producer())
        accum: list[str] = []
        while True:
            kind, value = loop.run_until_complete(queue.get())
            if kind == "delta":
                accum.append(value)
                yield _sse("delta", {"partial": "".join(accum)})
            elif kind == "done":
                session = InterviewSession.objects.get(id=value)
                last_decision = (session.decision_log or [])[-1] if session.decision_log else {}
                yield _sse(
                    "done",
                    {
                        "assistant_text": "".join(accum),
                        "decision": last_decision,
                        "session_status": session.status,
                    },
                )
            elif kind == "error":
                yield _sse("error", {"message": value})
            elif kind == "__end__":
                break
        loop.run_until_complete(producer_task)
    finally:
        loop.close()


@csrf_exempt
@require_http_methods(["POST"])
def post_message(
    request: HttpRequest, session_id: str
) -> StreamingHttpResponse | JsonResponse:
    """Entry point for text-mode interview turns."""
    try:
        session = InterviewSession.objects.select_related(
            "study", "guide", "participation"
        ).get(id=session_id)
    except InterviewSession.DoesNotExist:
        return JsonResponse({"error": "session_not_found"}, status=404)

    if not _authorize(request, session):
        return JsonResponse({"error": "unauthorized"}, status=403)

    try:
        payload = json.loads(request.body or b"{}")
    except Exception:
        payload = {}
    message = (payload.get("message") or "").strip()
    if not message:
        return JsonResponse({"error": "message_required"}, status=400)

    with bind_trace(trace_id=session.trace_id, session_id=str(session.id)):
        response = StreamingHttpResponse(
            _stream_bytes(str(session.id), message),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
