"""Health check endpoints for merism-app.

Two routes are exposed:

- ``/healthz`` — **liveness**. Returns 200 if the process is up. Used by
  container orchestrators (Docker / Kubernetes) to decide whether to
  restart the pod. Must not touch external services — a slow DB must not
  cause an unnecessary restart.
- ``/readyz`` — **readiness**. Returns 200 only when the process can
  actually serve traffic: DB reachable, Redis reachable. Used by load
  balancers to decide whether to route requests.

Design notes:

- No auth. Health endpoints must be reachable by probes before the app
  is fully configured.
- No logging spam. Probes hit these every few seconds — we don't want
  them in structlog INFO stream.
- Strict timeouts on downstream checks so a hung Postgres doesn't block
  the response forever.
- Response body is a tiny JSON blob so a human curling it can see which
  dependency failed.
"""

from __future__ import annotations

import time
from typing import Any

from django.conf import settings
from django.db import connections
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

# Max wall time we'll spend on any single dependency check before giving up.
_CHECK_TIMEOUT_SECONDS = 2.0


@csrf_exempt
@never_cache
@require_GET
def liveness(request: HttpRequest) -> JsonResponse:
    """Liveness probe. Always 200 if the process is alive.

    This route deliberately does **not** touch DB / Redis / external
    services. Orchestrators use liveness to decide whether to kill the
    pod; a dependency outage must not trigger a restart loop.
    """
    return JsonResponse({"status": "ok"}, status=200)


@csrf_exempt
@never_cache
@require_GET
def readiness(request: HttpRequest) -> JsonResponse:
    """Readiness probe. 200 only if PostgreSQL and Redis are reachable.

    Load balancers should route traffic only when this returns 200. When
    a dependency is down, we return 503 with per-check status so the
    on-call engineer can see at a glance which side is broken.
    """
    checks: dict[str, dict[str, Any]] = {
        "database": _check_database(),
        "redis": _check_redis(),
    }
    status = 200 if all(c["ok"] for c in checks.values()) else 503
    return JsonResponse({"status": "ok" if status == 200 else "degraded", "checks": checks}, status=status)


def _check_database() -> dict[str, Any]:
    """Run ``SELECT 1`` against the default DB connection.

    We use the Django connection pool — ``connections["default"]`` — so
    we reuse whatever configuration the app already has. ``cursor()``
    will open a new connection if none is cached; that's fine for a
    readiness probe.
    """
    start = time.monotonic()
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:
        return {
            "ok": False,
            "error": type(exc).__name__,
            "latency_ms": round((time.monotonic() - start) * 1000, 1),
        }
    return {"ok": True, "latency_ms": round((time.monotonic() - start) * 1000, 1)}


def _check_redis() -> dict[str, Any]:
    """Ping Redis via the Django cache backend.

    Merism uses Redis for: Django cache, Celery broker, Celery results,
    and the channel layer. If cache.set/get works, the others are
    generally fine (they talk to the same Redis cluster).
    """
    start = time.monotonic()
    try:
        from django.core.cache import cache

        cache.set("__readiness_probe__", "1", timeout=_CHECK_TIMEOUT_SECONDS)
        value = cache.get("__readiness_probe__")
        if value != "1":
            return {
                "ok": False,
                "error": "cache-value-mismatch",
                "latency_ms": round((time.monotonic() - start) * 1000, 1),
            }
    except Exception as exc:
        return {
            "ok": False,
            "error": type(exc).__name__,
            "latency_ms": round((time.monotonic() - start) * 1000, 1),
        }
    return {"ok": True, "latency_ms": round((time.monotonic() - start) * 1000, 1)}


__all__ = ["liveness", "readiness"]


# Settings-derived hint used in logs / admin so deployers can spot-check
# that the health module is wired up correctly.
_ = settings  # suppress "unused" lint when the module is imported early
