"""Trace binding helpers.

Used to attach a ``trace_id`` (typically ``Participation.trace_id``) to
the structlog context for the duration of a unit of work. All logs
emitted inside the ``with bind_trace(...)`` block carry the id
automatically.

Usage
-----

    from merism.observability import bind_trace

    with bind_trace(trace_id=participation.trace_id):
        do_work()

``trace_id`` is the single correlation handle for the invite→consent
→session→insight pipeline; it lives on every table touched by that
pipeline so logs, DB rows, and events can be cross-joined at any layer.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any, Iterator
from uuid import UUID

import structlog

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def bind_trace(
    *, trace_id: UUID | str | None, **extras: Any
) -> Iterator[None]:
    """Bind a ``trace_id`` (and optional extras) onto the structlog contextvars.

    Clears the added keys on exit even if the block raises. Nested calls
    stack correctly thanks to structlog's contextvars processor.
    """
    tid = str(trace_id) if trace_id is not None else None
    payload: dict[str, Any] = {k: v for k, v in extras.items() if v is not None}
    if tid is not None:
        payload["trace_id"] = tid
    tokens = structlog.contextvars.bind_contextvars(**payload)
    try:
        yield
    finally:
        # bind_contextvars doesn't return tokens in all structlog versions;
        # unbind explicitly using the keys we added.
        structlog.contextvars.unbind_contextvars(*payload.keys())
