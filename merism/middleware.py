"""Security response-header middleware.

Django's built-in :class:`SecurityMiddleware` already sets HSTS,
``X-Content-Type-Options``, ``X-Frame-Options``, and ``Referrer-Policy``.
What it does not set is:

- ``Content-Security-Policy`` — controls what origins the browser may
  load scripts / images / connections / frames from. This is the main
  mitigation against XSS.
- ``Permissions-Policy`` — tells the browser which capabilities (camera,
  microphone, geolocation, …) the page is allowed to use. Merism needs
  microphone access for the voice interview room; everything else is
  explicitly denied.

We write those two headers here. Every response runs through this
middleware, including the admin, DRF API, and static files served via
Django (dev only — in prod a reverse proxy serves static).

Tuning:

- Override ``settings.MERISM_CSP`` to replace the default CSP string.
- Override ``settings.MERISM_PERMISSIONS_POLICY`` similarly.
- Per-view overrides win (a view that sets the header itself is not
  overwritten).
"""

from __future__ import annotations

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse


# Production CSP — conservative but doesn't break django-unfold admin
# (which ships with inline style attributes).
_DEFAULT_CSP_PROD = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "media-src 'self' blob:; "
    "object-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

# Dev CSP additionally allows Vite HMR (ws://localhost:5173) and eval
# (vite's hot-module-reload uses ``new Function``).
_DEFAULT_CSP_DEV = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "font-src 'self' data:; "
    "connect-src 'self' ws: wss: http://localhost:5173 http://127.0.0.1:5173; "
    "media-src 'self' blob:; "
    "object-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'"
)

# Permissions-Policy — explicitly disable every feature we don't need.
# ``microphone=(self)`` is required for the voice interview room.
# ``camera=()`` is disabled until the video interview room ships.
_DEFAULT_PERMISSIONS_POLICY = (
    "microphone=(self), "
    "camera=(), "
    "geolocation=(), "
    "payment=(), "
    "usb=(), "
    "accelerometer=(), "
    "gyroscope=(), "
    "magnetometer=(), "
    "fullscreen=(self)"
)


class SecurityHeadersMiddleware:
    """Append ``Content-Security-Policy`` and ``Permissions-Policy`` to every
    response (unless the view already set them)."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        if "Content-Security-Policy" not in response.headers:
            csp = getattr(settings, "MERISM_CSP", None)
            if csp is None:
                csp = _DEFAULT_CSP_DEV if settings.DEBUG else _DEFAULT_CSP_PROD
            response["Content-Security-Policy"] = csp

        if "Permissions-Policy" not in response.headers:
            response["Permissions-Policy"] = getattr(
                settings, "MERISM_PERMISSIONS_POLICY", _DEFAULT_PERMISSIONS_POLICY
            )

        return response


__all__ = ["SecurityHeadersMiddleware"]
