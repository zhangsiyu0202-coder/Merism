"""Channels WebSocket routing for Merism realtime."""

from __future__ import annotations

from django.urls import re_path

from merism.realtime.voice import VoiceConsumerV2

websocket_urlpatterns = [
    re_path(
        r"^ws/sessions/(?P<session_id>[0-9a-fA-F-]+)/voice/?$",
        VoiceConsumerV2.as_asgi(),
        name="voice_ws",
    ),
]
