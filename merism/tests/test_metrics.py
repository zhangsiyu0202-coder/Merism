"""Prometheus /metrics endpoint behaviour."""

from __future__ import annotations

import pytest
from django.test import Client


pytestmark = pytest.mark.django_db


class TestMetricsEndpoint:
    def test_returns_200(self) -> None:
        client = Client()
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_content_type_is_prometheus(self) -> None:
        client = Client()
        response = client.get("/metrics")
        # django_prometheus emits the standard OpenMetrics content-type.
        ctype = response.headers["Content-Type"]
        assert "text/plain" in ctype
        assert "version=" in ctype

    def test_body_has_merism_traffic_metrics(self) -> None:
        """The metrics body should include at least one well-known
        django-prometheus counter. Hit the liveness endpoint first so
        the ``django_http_requests_total_by_method_total`` counter is
        non-empty when we scrape.
        """
        client = Client()
        client.get("/healthz")  # populate counters
        response = client.get("/metrics")
        text = response.content.decode("utf-8")

        # django-prometheus default metric families.
        assert "# HELP python_info" in text
        assert "django_http_requests_total_by_method_total" in text
        # And a metric sample for the GET we just issued.
        assert 'django_http_requests_total_by_method_total{method="GET"}' in text
