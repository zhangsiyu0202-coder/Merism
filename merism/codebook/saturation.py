"""Codebook saturation detection.

Determines whether a study's codebook has stabilized (no new codes
emerging from recent sessions).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from asgiref.sync import sync_to_async

if TYPE_CHECKING:
    from merism.models import Study

from merism.codebook.models import CodeChange


@sync_to_async
def is_codebook_saturated(study: Study, lookback: int = 3) -> bool:
    """True if last `lookback` sessions produced no new applied 'add' changes."""
    from merism.models import InterviewSession

    recent_sessions = list(
        InterviewSession.objects.filter(study=study, status="completed")
        .order_by("-completed_at")[:lookback]
    )
    if len(recent_sessions) < lookback:
        return False

    oldest = recent_sessions[-1]
    new_adds = CodeChange.objects.filter(
        study=study,
        change_type=CodeChange.ChangeType.ADD,
        status=CodeChange.Status.APPLIED,
        created_at__gte=oldest.completed_at,
    ).count()
    return new_adds == 0
