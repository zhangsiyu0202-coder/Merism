"""ASGI application entry point for Merism.

HTTP goes to Django's standard ASGI handler; ``ws://host/ws/*`` routes
through Django Channels to the voice consumer and any future WebSocket
surfaces (researcher observation stream, live dashboard, etc.).
"""

from __future__ import annotations

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "merism.settings.dev")

# IMPORTANT: initialise Django BEFORE importing Channels routing so that
# ``AppConfig.ready()`` has run and ORM imports inside consumers work.
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402 — see comment above
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

from merism.realtime.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
