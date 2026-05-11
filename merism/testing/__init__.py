"""Merism test harness — pytest-native helpers, factories, fakes, assertions.

Thin public surface: only the most-used symbols are re-exported here. Less-common
helpers live in submodules and should be imported explicitly, e.g.::

    from merism.testing.factories.knowledge import make_knowledge_chunk
    from merism.testing.fakes.redis import fakeredis_monkeypatch

See :mod:`merism.testing.README` for writing conventions and a migration guide
from ``posthog.test.base``.
"""

from __future__ import annotations

from typing import Any

# ── Base test classes (eager, DRF-free) ────────────────────
from merism.testing.base import (
    MerismSmokeTest,
    MerismTestCase,
    MerismTransactionTestCase,
)

# ── Most-used factories ─────────────────────────────────────
from merism.testing.factories.interview import make_interview, make_turn
from merism.testing.factories.study import make_study, make_study_with_goals

# ── Most-used fakes ─────────────────────────────────────────
from merism.testing.fakes.im_channel import InMemoryIMAdapter
from merism.testing.fakes.llm import DeterministicLLM
from merism.testing.fakes.sse import SSETestClient

# ── Most-used assertions ────────────────────────────────────
from merism.testing.assertions import (
    FuzzyInt,
    assert_conductor_phase,
    assert_goal_coverage_close_to,
    assert_no_posthog_modules_loaded,
    assert_sse_sequence,
)


def __getattr__(name: str) -> Any:
    """Lazy resolution for ``MerismAPITestCase``.

    DRF imports Django settings at module load time. Defer it so
    ``import merism.testing`` works even before Django is configured.
    """
    if name == "MerismAPITestCase":
        from merism.testing.base import MerismAPITestCase  # triggers DRF import

        globals()["MerismAPITestCase"] = MerismAPITestCase
        return MerismAPITestCase
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    # Base
    "MerismTestCase",
    "MerismAPITestCase",
    "MerismTransactionTestCase",
    "MerismSmokeTest",
    # Factories (common)
    "make_study",
    "make_study_with_goals",
    "make_interview",
    "make_turn",
    # Fakes (common)
    "DeterministicLLM",
    "InMemoryIMAdapter",
    "SSETestClient",
    # Assertions (common)
    "assert_conductor_phase",
    "assert_goal_coverage_close_to",
    "assert_sse_sequence",
    "assert_no_posthog_modules_loaded",
    "FuzzyInt",
]
