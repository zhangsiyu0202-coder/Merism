# `merism.realtime`

Interview room real-time transport. Redis-backed, ASGI-native.

## Task list (R8 follow-up)

1. **`sse_interview.py`** — async generator that yields SSE events from a
   Redis Stream keyed by session id. Supports `Last-Event-ID` for
   reconnect replay (critical for flaky mobile networks during
   participant interviews).
2. **`sse_views.py`** — DRF `APIView` that returns a `StreamingHttpResponse`
   wrapping `sse_interview.stream()`. Mount under
   `/api/interviews/<session_id>/stream/`.
3. **`voice_protocol.py`** — Pydantic models for WS messages
   (`AudioChunk`, `PartialTranscript`, `FinalTranscript`, `AIText`,
   `AIAudioChunk`, `DecisionEvent`).
4. **`consumers.py`** — Django Channels `AsyncConsumer`s (or fall back to
   a raw ASGI + `websockets` pattern if we skip Channels). Handles both
   the participant voice stream and the researcher observation stream.
5. **`xadd_helpers.py`** — monotonic ID generation for Redis `XADD`
   with maxlen truncation. Ported from old repo's
   `merism/interview_sse/_core.py` once we need it.
6. **Tests** using `merism.testing.fakes.SSETestClient` +
   `merism.testing.fakes.redis.fakeredis_monkeypatch`.

## Key design choices

- One stream key per session (`merism:session:{id}:events`).
- Maxlen per stream: 5000 events (a 60-min voice interview averages ~1500
  events so this gives headroom).
- Event payload is JSON with `event` + `data` + optional `id` fields
  matching SSE wire format.
