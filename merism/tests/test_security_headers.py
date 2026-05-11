"""SecurityHeadersMiddleware behaviour."""

from __future__ import annotations

import pytest
from django.test import Client, override_settings


pytestmark = pytest.mark.django_db


class TestContentSecurityPolicy:
    def test_csp_header_set_on_every_response(self) -> None:
        client = Client()
        response = client.get("/healthz")
        assert "Content-Security-Policy" in response.headers

    def test_csp_contains_hardening_directives(self) -> None:
        client = Client()
        response = client.get("/healthz")
        csp = response.headers["Content-Security-Policy"]
        # Core hardening — same in dev and prod.
        assert "default-src 'self'" in csp
        assert "object-src 'none'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "base-uri 'self'" in csp

    def test_csp_can_be_overridden_by_view(self) -> None:
        """If a view sets CSP itself, the middleware must not overwrite it."""
        from django.http import HttpResponse

        resp = HttpResponse("ok")
        resp["Content-Security-Policy"] = "default-src 'none'"

        # Simulate middleware processing — directly instantiate and call.
        from merism.middleware import SecurityHeadersMiddleware

        middleware = SecurityHeadersMiddleware(get_response=lambda req: resp)
        out = middleware(request=None)  # type: ignore[arg-type]
        assert out["Content-Security-Policy"] == "default-src 'none'"

    def test_csp_setting_override_is_respected(self) -> None:
        with override_settings(MERISM_CSP="default-src 'self' https://example.com"):
            client = Client()
            response = client.get("/healthz")
            assert response.headers["Content-Security-Policy"] == (
                "default-src 'self' https://example.com"
            )


class TestPermissionsPolicy:
    def test_permissions_policy_set(self) -> None:
        client = Client()
        response = client.get("/healthz")
        assert "Permissions-Policy" in response.headers

    def test_microphone_allowed_for_self(self) -> None:
        """Voice interview room needs microphone access on the same origin."""
        client = Client()
        response = client.get("/healthz")
        pp = response.headers["Permissions-Policy"]
        assert "microphone=(self)" in pp

    def test_camera_disabled_until_video_room_ships(self) -> None:
        client = Client()
        response = client.get("/healthz")
        pp = response.headers["Permissions-Policy"]
        assert "camera=()" in pp

    def test_geolocation_disabled(self) -> None:
        client = Client()
        response = client.get("/healthz")
        pp = response.headers["Permissions-Policy"]
        assert "geolocation=()" in pp
