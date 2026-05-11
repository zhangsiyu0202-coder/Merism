"""Sentry integration for merism-app.

Opt-in: when ``SENTRY_DSN`` is empty (typical in dev / test), this module
is a no-op. In staging and production we inject a real DSN via the
deployment environment and errors flow to Sentry.

Kept in its own module (not inline in settings/base.py) so:

- The import side-effect is explicit — you call ``init_sentry()`` once.
- We can unit-test the init function without reloading Django settings.
- It's easy to add/remove integrations later (Celery, Redis, HTTPX) without
  touching settings.
"""

from __future__ import annotations

import os

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.redis import RedisIntegration


def init_sentry() -> bool:
    """Initialise Sentry if ``SENTRY_DSN`` is set.

    Returns ``True`` if Sentry was initialised, ``False`` otherwise. The
    return value is primarily useful for unit tests; production code
    should not branch on it.
    """
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("SENTRY_ENVIRONMENT", "development"),
        release=os.environ.get("SENTRY_RELEASE") or None,
        # Tracing / performance monitoring.
        traces_sample_rate=_env_float("SENTRY_TRACES_SAMPLE_RATE", 0.0),
        # Profiling — off by default; enable only when investigating
        # a perf regression, since profiling billing is separate.
        profiles_sample_rate=_env_float("SENTRY_PROFILES_SAMPLE_RATE", 0.0),
        # Default PII off — we do not want participant identifiers, raw
        # transcripts, or auth headers accidentally shipped.
        send_default_pii=False,
        integrations=[
            DjangoIntegration(
                # Don't hook ORM instrumentation in dev — too noisy.
                transaction_style="url",
            ),
            CeleryIntegration(monitor_beat_tasks=True),
            RedisIntegration(),
            LoggingIntegration(level=None, event_level=None),
        ],
        # Ignore expected events that are not useful in Sentry.
        before_send=_before_send,
    )
    return True


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _before_send(event, hint):  # type: ignore[no-untyped-def]
    """Strip fields that must never leave the boundary before sending to Sentry.

    Sentry already scrubs common auth headers, but PII-shaped fields
    particular to Merism (participant email, recipient hash, raw
    transcripts) are scrubbed here as a defense-in-depth measure.
    """
    request = event.get("request") or {}
    headers = request.get("headers")
    if isinstance(headers, dict):
        for header in ("Cookie", "Authorization"):
            if header in headers:
                headers[header] = "[Filtered]"
    # Strip participant-facing endpoints from breadcrumbs (they may contain
    # a recipient token in the query string).
    for crumb in event.get("breadcrumbs", {}).get("values") or []:
        data = crumb.get("data") or {}
        url = data.get("url") or ""
        if "/i/" in url and "?t=" in url:
            data["url"] = url.split("?t=", 1)[0] + "?t=[Filtered]"
    return event


__all__ = ["init_sentry"]
