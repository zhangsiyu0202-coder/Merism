"""Merism realtime layer — SSE + WebSocket.

Public surface:

- :func:`merism.realtime.sse_interview.iter_session_sse` — async generator
  of SSE byte chunks for one session (researcher observation + replay).
- :func:`merism.realtime.sse_interview.publish_session_event` — XADD a
  single event to the session stream.
- :class:`merism.realtime.voice.VoiceConsumer` — WebSocket consumer for
  the participant voice channel (bi-directional PCM / CosyVoice audio
  + Paraformer STT + moderator orchestration, with optional barge-in
  per ADR 0002).
- :mod:`merism.realtime.voice_protocol` — Pydantic message types for
  the WS control plane.
- :mod:`merism.realtime.routing` — Channels URL routing.
"""

from __future__ import annotations

from merism.realtime.sse_interview import (
    iter_session_sse,
    publish_session_event,
)
from merism.realtime.voice import VoiceConsumerV2 as VoiceConsumer

__all__ = [
    "iter_session_sse",
    "publish_session_event",
    "VoiceConsumer",
]
