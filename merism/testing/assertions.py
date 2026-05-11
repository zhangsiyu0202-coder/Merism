"""Merism-specific assertions.

Use these instead of hand-rolled ``assert`` statements so failures produce
domain-aware error messages and the call sites read like sentences about the
product, not plumbing.
"""

from __future__ import annotations

import sys
from typing import Any, Iterable

__all__ = [
    "FuzzyInt",
    "assert_conductor_phase",
    "assert_next_action",
    "assert_goal_coverage_close_to",
    "assert_citation_chain",
    "assert_sse_sequence",
    "assert_broadcast_status",
    "assert_delivery_sent_to",
    "assert_block_valid",
    "assert_policy_fired",
    "assert_no_posthog_modules_loaded",
]


# ─── Query-count / numeric assertions ───────────────────────


class FuzzyInt(int):
    """``int`` subclass that compares equal to any value within ``[lowest, highest]``.

    Useful for query count assertions that flap due to test ordering / cache
    warm-up. Example::

        with self.assertNumQueries(FuzzyInt(3, 5)):
            study_list_view()
    """

    lowest: int
    highest: int

    def __new__(cls, lowest: int, highest: int) -> "FuzzyInt":
        obj = super().__new__(cls, highest)
        obj.lowest = lowest
        obj.highest = highest
        return obj

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, int):
            return NotImplemented
        return self.lowest <= other <= self.highest

    def __ne__(self, other: object) -> bool:
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __hash__(self) -> int:
        return hash((self.lowest, self.highest))

    def __repr__(self) -> str:
        return f"[{self.lowest:d}..{self.highest:d}]"


# ─── Conductor assertions ───────────────────────────────────


def assert_conductor_phase(state: Any, *, expected: str) -> None:
    """Assert the conductor ``phase`` matches ``expected``.

    Valid phases: ``"warmup"``, ``"active"``, ``"closing"``, ``"ended"``.
    """
    phase = getattr(state, "phase", None)
    if phase != expected:
        raise AssertionError(
            f"Expected conductor phase == {expected!r}, got {phase!r}"
        )


def assert_next_action(state: Any, *, expected: str) -> None:
    """Assert the Meso-layer ``next_action`` matches ``expected``.

    Typical values: ``"deepen"`` / ``"move_on"`` / ``"clarify"`` / ``"steer"`` / ``"end"``.
    """
    actual = getattr(state, "next_action", None)
    if actual != expected:
        raise AssertionError(
            f"Expected conductor next_action == {expected!r}, got {actual!r}"
        )


def assert_policy_fired(policy_result: Any, *, expected_policy: str) -> None:
    """Assert that the given policy layer produced a decision (``policy_result`` not None)
    and that its ``kind`` / ``policy`` field matches ``expected_policy``.
    """
    if policy_result is None:
        raise AssertionError(
            f"Expected policy {expected_policy!r} to fire, got no decision"
        )
    kind = getattr(policy_result, "policy", None) or getattr(policy_result, "kind", None)
    if kind != expected_policy:
        raise AssertionError(
            f"Expected policy {expected_policy!r} to fire, got {kind!r}"
        )


# ─── Goal coverage ──────────────────────────────────────────


def assert_goal_coverage_close_to(
    goal: Any, *, expected: float, tolerance: float = 0.05
) -> None:
    """Assert ``goal.coverage`` is within ``tolerance`` of ``expected``."""
    actual = float(getattr(goal, "coverage", 0.0))
    if abs(actual - expected) > tolerance:
        raise AssertionError(
            f"Goal {getattr(goal, 'question', goal)!r} coverage={actual:.3f}, "
            f"expected {expected:.3f}±{tolerance:.3f}"
        )


# ─── Citation chain (Ask Merism / RAG) ──────────────────────


def assert_citation_chain(
    carrier: Any,
    *,
    expected_source_ids: Iterable[str | int],
) -> None:
    """Assert that ``carrier`` (e.g., Decision / Report block / RAG answer)
    cites each id in ``expected_source_ids`` in order.

    The carrier must expose one of ``citations``, ``source_ids``, or ``sources``.
    Each element must have ``id``.
    """
    expected = [str(x) for x in expected_source_ids]
    citations = (
        getattr(carrier, "citations", None)
        or getattr(carrier, "source_ids", None)
        or getattr(carrier, "sources", None)
        or []
    )
    actual = [str(getattr(c, "id", c)) for c in citations]
    if actual != expected:
        raise AssertionError(
            f"Citation chain mismatch.\n  expected: {expected}\n  actual:   {actual}"
        )


# ─── SSE sequence ───────────────────────────────────────────


def assert_sse_sequence(client_or_events: Any, *, expected: list[str]) -> None:
    """Assert the SSE event names emitted in order match ``expected``.

    ``client_or_events`` can be:
    - an :class:`merism.testing.fakes.sse.SSETestClient`
    - a list of events with ``.event`` attr
    - a list of strings (event names)
    """
    events = getattr(client_or_events, "events", client_or_events)
    if not isinstance(events, list):
        events = list(events)
    actual = [e.event if hasattr(e, "event") else str(e) for e in events]
    if actual != expected:
        raise AssertionError(
            f"SSE sequence mismatch.\n  expected: {expected}\n  actual:   {actual}"
        )


# ─── Recruitment assertions ─────────────────────────────────


def assert_broadcast_status(broadcast: Any, expected: str) -> None:
    actual = getattr(broadcast, "status", None)
    if actual != expected:
        raise AssertionError(
            f"Broadcast {getattr(broadcast, 'id', '?')} status={actual!r}, expected {expected!r}"
        )


def assert_delivery_sent_to(adapter: Any, recipient_id: str) -> None:
    """Assert the in-memory IM adapter delivered at least one message to ``recipient_id``."""
    messages_to = getattr(adapter, "messages_to", None)
    if not callable(messages_to):
        raise AssertionError(
            f"{adapter!r} does not look like an InMemoryIMAdapter (no messages_to helper)"
        )
    delivered = messages_to(recipient_id)
    if not delivered:
        recipients = sorted({m.recipient_id for m in getattr(adapter, "sent_messages", [])})
        raise AssertionError(
            f"No messages delivered to {recipient_id!r}. "
            f"Delivered to: {recipients}"
        )


# ─── Report block validation ────────────────────────────────


def assert_block_valid(block: dict[str, Any]) -> None:
    """Assert a single report block matches the text/metric/quote/chart schema.

    Kept intentionally minimal — the real schema validator lives in
    ``products/studies/backend/reports/schema.py`` and is exercised there.
    This helper is for quick shape checks in tests that don't want to import
    the full pydantic model.
    """
    kind = block.get("type") if isinstance(block, dict) else None
    if kind not in {"text", "metric", "quote", "chart"}:
        raise AssertionError(
            f"Block type must be one of text/metric/quote/chart, got {kind!r}"
        )
    if kind == "text" and not block.get("body"):
        raise AssertionError("text block is missing 'body'")
    if kind == "metric" and ("label" not in block or "value" not in block):
        raise AssertionError("metric block requires 'label' and 'value'")
    if kind == "quote" and not block.get("source"):
        raise AssertionError("quote block requires 'source'")
    if kind == "chart" and not block.get("series"):
        raise AssertionError("chart block requires 'series'")


# ─── Boundary assertions (test-harness self-check) ──────────


def assert_no_posthog_modules_loaded() -> None:
    """Fail if any ``posthog.*`` module is loaded in ``sys.modules``.

    Use in boundary tests to catch accidental PostHog coupling in Merism code.
    """
    offenders = sorted(m for m in sys.modules if m == "posthog" or m.startswith("posthog."))
    if offenders:
        raise AssertionError(
            "PostHog modules leaked into the Merism test boundary:\n  - "
            + "\n  - ".join(offenders[:20])
            + ("\n  ..." if len(offenders) > 20 else "")
        )
