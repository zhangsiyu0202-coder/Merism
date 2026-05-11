"""Shared ``fakeredis`` setup for Merism tests.

Merism uses Redis in two places tests care about:

1. Per-team / per-IP throttling (token bucket).
2. Interview SSE replay stream (Redis streams with ``XADD`` / ``XREAD``).

Tests across Studies used to copy-paste a ``_fakeredis_throttle`` /
``_fakeredis_monkeypatch`` fixture per file. This module collects the pattern
so new tests can write::

    from merism.testing.fakes.redis import fakeredis_monkeypatch

    @pytest.fixture
    def _fake_redis(monkeypatch):
        yield from fakeredis_monkeypatch(monkeypatch)

or, with the broken-eval variant::

    from merism.testing.fakes.redis import BrokenEvalRedis

    monkeypatch.setattr("django_redis.get_redis_connection", lambda alias=None, **_: BrokenEvalRedis())
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

try:
    import fakeredis
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "merism.testing.fakes.redis requires the 'fakeredis' package. "
        "It is already listed in pyproject.toml dev deps; run `uv sync`."
    ) from exc


class BrokenEvalRedis(fakeredis.FakeRedis):
    """``fakeredis`` variant that raises on ``eval``/``evalsha``.

    Use to verify fail-open behavior in throttle / stream code paths when Redis
    Lua execution errors out.
    """

    def eval(self, *_: Any, **__: Any) -> Any:  # pragma: no cover - exercised via tests
        raise RuntimeError("BrokenEvalRedis: eval deliberately disabled for tests")

    def evalsha(self, *_: Any, **__: Any) -> Any:  # pragma: no cover
        raise RuntimeError("BrokenEvalRedis: evalsha deliberately disabled for tests")


def make_fake_redis(**_: Any) -> fakeredis.FakeRedis:
    """Factory matching the signature of ``django_redis.get_redis_connection``."""
    return fakeredis.FakeRedis(decode_responses=False)


def fakeredis_monkeypatch(monkeypatch: Any) -> Iterator[fakeredis.FakeRedis]:
    """Install a fakeredis client for every ``get_redis_connection()`` call.

    Yields the shared instance so a single test can pre-seed keys / check state.
    """
    client = fakeredis.FakeRedis(decode_responses=False)

    def _fake_connection(alias: str | None = None, **_: Any) -> fakeredis.FakeRedis:
        return client

    # Patch the common Redis entry points used across Merism.
    monkeypatch.setattr("django_redis.get_redis_connection", _fake_connection, raising=False)

    yield client

    client.flushall()


def fakeredis_broken_monkeypatch(monkeypatch: Any) -> Iterator[BrokenEvalRedis]:
    """Install a Redis client whose ``eval`` always raises.

    Used to test fail-open behaviour (throttle returns allowed, SSE degrades,
    etc.) when Redis scripting fails.
    """
    client = BrokenEvalRedis(decode_responses=False)
    monkeypatch.setattr(
        "django_redis.get_redis_connection",
        lambda alias=None, **_: client,
        raising=False,
    )
    yield client
    client.flushall()
