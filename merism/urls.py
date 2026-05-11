"""Merism URL configuration.

Domain-level routers are mounted from their own ``urls`` modules as they come
online. Today only admin + schema endpoints exist.
"""

from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from merism.health import liveness, readiness

urlpatterns = [
    # Health probes (k8s / Docker / LB). No auth, no CSRF, no cache.
    # Keep these near the top so a misrouted /admin/ rule can't shadow them.
    path("healthz", liveness, name="healthz"),
    path("readyz", readiness, name="readyz"),

    # Prometheus metrics — scraped by infrastructure, not by end users.
    # Mount at root so the conventional /metrics URL works; the include
    # registers just that one route.
    path("", include("django_prometheus.urls")),

    path("admin/", admin.site.urls),
    # django-allauth (ADR 0001) — login / signup / email confirmation /
    # social OAuth under /accounts/.
    path("accounts/", include("allauth.urls")),
    # OpenAPI schema + interactive docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # Main API router (studies / interviews / knowledge / recruitment / reports / memai)
    path("api/", include("merism.api.urls")),
    # Anonymous participant entry — see merism/participant/design.md
    path("i/", include("merism.participant.urls")),
]
