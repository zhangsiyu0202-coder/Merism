"""Tests for the /healthz and /readyz probes."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from django.test import Client


pytestmark = pytest.mark.django_db


class TestLiveness:
    def test_returns_200_ok(self) -> None:
        client = Client()
        response = client.get("/healthz")
        assert response.status_code == 200
        body = json.loads(response.content)
        assert body == {"status": "ok"}

    def test_accepts_only_get(self) -> None:
        client = Client()
        response = client.post("/healthz")
        assert response.status_code == 405  # Method Not Allowed

    def test_has_no_cache_header(self) -> None:
        client = Client()
        response = client.get("/healthz")
        cache_control = response.headers.get("Cache-Control", "")
        assert "no-cache" in cache_control or "no-store" in cache_control, cache_control


class TestReadiness:
    def test_returns_200_when_all_healthy(self) -> None:
        client = Client()
        response = client.get("/readyz")
        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["status"] == "ok"
        assert body["checks"]["database"]["ok"] is True
        assert body["checks"]["redis"]["ok"] is True
        assert "latency_ms" in body["checks"]["database"]
        assert "latency_ms" in body["checks"]["redis"]

    def test_returns_503_when_database_fails(self) -> None:
        client = Client()
        with patch("merism.health._check_database") as mock_db:
            mock_db.return_value = {"ok": False, "error": "OperationalError", "latency_ms": 1.0}
            response = client.get("/readyz")
        assert response.status_code == 503
        body = json.loads(response.content)
        assert body["status"] == "degraded"
        assert body["checks"]["database"]["ok"] is False
        assert body["checks"]["database"]["error"] == "OperationalError"

    def test_returns_503_when_redis_fails(self) -> None:
        client = Client()
        with patch("merism.health._check_redis") as mock_redis:
            mock_redis.return_value = {"ok": False, "error": "ConnectionError", "latency_ms": 2.0}
            response = client.get("/readyz")
        assert response.status_code == 503
        body = json.loads(response.content)
        assert body["status"] == "degraded"
        assert body["checks"]["redis"]["ok"] is False

    def test_accepts_only_get(self) -> None:
        client = Client()
        response = client.post("/readyz")
        assert response.status_code == 405
