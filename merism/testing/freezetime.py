"""Thin wrapper around ``freezegun`` for Merism-side ergonomic defaults.

Exposes :func:`frozen_time` with the same interface as ``freezegun.freeze_time``
plus a default moment (``2026-01-01T00:00:00Z``) for tests that don't care
which moment is frozen. Use it as a context manager or as a decorator::

    with frozen_time("2026-05-09T08:30:00+08:00") as f:
        run_something()
        f.tick(delta=timedelta(minutes=5))
"""

from __future__ import annotations

from datetime import datetime

try:
    from freezegun import freeze_time as _freeze_time
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "merism.testing.freezetime requires 'freezegun'. "
        "It is already in pyproject.toml dev deps; run `uv sync`."
    ) from exc


_DEFAULT_MOMENT = "2026-01-01T00:00:00+00:00"


def frozen_time(moment: str | datetime | None = None, *, tz_offset: int = 0):
    """Freeze time at ``moment`` (ISO-8601 string or datetime). Default: ``2026-01-01T00:00:00Z``.

    Direct re-export of ``freezegun.freeze_time`` with a convenient default so
    tests don't need to pick an arbitrary point.
    """
    return _freeze_time(moment if moment is not None else _DEFAULT_MOMENT, tz_offset=tz_offset)
