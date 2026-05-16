"""Codebook saturation detection.

Determines whether a study's codebook has stabilized (no new codes
emerging from recent sessions).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from merism.models import Study

from merism.codebook.models import CodeChange


def is_codebook_saturated(study: Study, lookback: int = 3) -> bool:
    """True if last `lookback` sessions produced no new applied 'add' changes."""
    from merism.models import InterviewSession

    recent_sessions = list(
        InterviewSession.objects.filter(
            study=study,
            status=InterviewSession.Status.COMPLETED,
            ended_at__isnull=False,
        )
        .order_by("-ended_at")[:lookback]
    )
    if len(recent_sessions) < lookback:
        return False

    oldest = recent_sessions[-1]
    threshold = oldest.ended_at or oldest.updated_at
    new_adds = CodeChange.objects.filter(
        study=study,
        change_type=CodeChange.ChangeType.ADD,
        status=CodeChange.Status.APPLIED,
        created_at__gte=threshold,
    ).count()
    return new_adds == 0
