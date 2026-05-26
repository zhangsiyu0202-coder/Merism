"""Process-wide compiled graph + checkpointer factory.

Both text-mode (HTTP) and voice-mode (pipecat) consumers need a long-lived
compiled :class:`~langgraph.graph.state.StateGraph` instance. This module
owns that instance — neither the text adapter nor the voice processor
should know how to build a graph; they ask the factory.

Decoupling rationale (per the 2026-05-23 voice-mode refactor):

- ``text_adapter`` previously owned ``get_graph`` and the connection pool.
  Voice mode ended up importing ``text_adapter.get_graph`` to share the
  cached instance — but that meant any change to the text adapter
  (checkpointer wiring, connection pool config) silently affected voice
  mode. Tests that exercised one mode would surface failures in the
  other.

- The factory has zero domain knowledge: it just builds a graph and
  caches the LangGraph checkpointer. Mode-specific glue lives in the
  callers (``text_adapter.py`` for HTTP, ``voice/setup.py`` for voice).

Backend selection:

- Postgres engine → :class:`PostgresSaver` with shared :class:`ConnectionPool`
- SQLite / dummy engine → :class:`InMemorySaver` (test path)

``setup()`` is idempotent at the SQL level (``CREATE TABLE IF NOT
EXISTS``) so concurrent boot of multiple workers is safe.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from typing import TYPE_CHECKING, Any

from django.conf import settings

from merism.conductor.graph import build_graph

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_graph_cache: Any = None
_pool_cache: Any = None
_saver_cache: Any = None
_build_lock = threading.Lock()


def _build_pg_dsn() -> str:
    """Construct a libpq DSN from Django's DATABASES settings."""
    db = settings.DATABASES["default"]
    return f"dbname={db['NAME']} user={db['USER']} password={db['PASSWORD']} host={db['HOST']} port={db['PORT']}"


def get_graph() -> Any:
    """Return the process-wide compiled v3 graph.

    Lazy: builds on first call, caches for subsequent calls.

    Backend choice driven by ``DATABASES["default"]["ENGINE"]``:
    - ``...postgresql`` → ``PostgresSaver`` with shared pool
    - anything else → ``InMemorySaver`` (test path)
    """
    global _graph_cache, _pool_cache, _saver_cache
    if _graph_cache is not None:
        return _graph_cache

    with _build_lock:
        if _graph_cache is not None:
            return _graph_cache

        engine = settings.DATABASES["default"].get("ENGINE", "")
        if engine.endswith("postgresql"):
            from langgraph.checkpoint.postgres import PostgresSaver
            from psycopg_pool import ConnectionPool

            _pool_cache = ConnectionPool(
                conninfo=_build_pg_dsn(),
                min_size=1,
                max_size=10,
                kwargs={"autocommit": True, "prepare_threshold": 0},
                open=True,
            )
            _saver_cache = PostgresSaver(_pool_cache)
            _saver_cache.setup()
            _graph_cache = build_graph(checkpointer=_saver_cache)
            logger.info("conductor.factory.graph_built checkpointer=PostgresSaver")
        else:
            from langgraph.checkpoint.memory import InMemorySaver

            _saver_cache = InMemorySaver()
            _graph_cache = build_graph(checkpointer=_saver_cache)
            logger.info(
                "conductor.factory.graph_built checkpointer=InMemorySaver (engine=%s)",
                engine,
            )
        return _graph_cache


def reset_graph_cache() -> None:
    """Test helper — wipe the cached graph + pool.

    Production code never calls this. Tests reusing the process should
    invoke this between cases to avoid checkpoint leakage and to let
    each test pass its own ``checkpointer`` (e.g. via ``build_graph``).
    """
    global _graph_cache, _pool_cache, _saver_cache
    if _pool_cache is not None:
        with contextlib.suppress(Exception):
            _pool_cache.close()
    _graph_cache = None
    _pool_cache = None
    _saver_cache = None


__all__ = ["get_graph", "reset_graph_cache"]
