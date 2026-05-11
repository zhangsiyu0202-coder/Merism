"""Channels WebSocket routing for Merism realtime.

Mounted by :mod:`merism.asgi`. Add more routes here as new WS surfaces
come online (e.g., researcher-side observation stream).
"""

from __future__ import annotations

from django.urls import re_path

from merism.realtime.voice import VoiceConsumer

websocket_urlpatterns = [
    re_path(
        r"^ws/sessions/(?P<session_id>[0-9a-fA-F-]+)/voice/?$",
        VoiceConsumer.as_asgi(),
        name="voice_ws",
    ),
]
