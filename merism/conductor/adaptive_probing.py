"""Coverage-aware moderator helper.

Produces a compact ``coverage_context`` string injected into the
moderator system prompt. The LLM uses it to decide whether to
bias the next probe toward an under-covered StudyGoal.

Kept small and cheap: just the latest CoverageSnapshot's gaps list,
rendered as one bullet per under-covered P0/P1 goal.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from asgiref.sync import sync_to_async

from merism.models import CoverageSnapshot

logger = logging.getLogger(__name__)


async def build_coverage_context(study_id: str | UUID) -> str:
    """Return a short text block describing coverage gaps, or '' if none.

    Example output:
        P0 goals still light (<30% coverage):
        - "Why do users churn at day 14?" (0.20, 2/10 sessions)
        - "What alternative did they switch to?" (0.10, 1/10 sessions)
        Consider steering toward these when the participant opens a door.
    """
    snapshot = await _latest_snapshot(study_id)
    if snapshot is None:
        return ""

    gaps = snapshot.gaps or []
    # Only surface P0 / P1 gaps — P2 is noise
    notable = [g for g in gaps if g.get("priority") in {"P0", "P1"}]
    if not notable:
        return ""

    lines = ["Under-covered goals (consider probing toward these):"]
    for g in notable[:5]:
        coverage = g.get("coverage", 0.0)
        matched = g.get("sessions_matched", 0)
        total = g.get("sessions_total", 0)
        lines.append(
            f'- [{g["priority"]}] "{g["goal_text"][:80]}" '
            f"(coverage {coverage:.0%}, {matched}/{total} sessions)"
        )
    return "\n".join(lines)


@sync_to_async
def _latest_snapshot(study_id: str | UUID) -> CoverageSnapshot | None:
    return (
        CoverageSnapshot.objects.filter(study_id=study_id)
        .order_by("-created_at")
        .first()
    )
