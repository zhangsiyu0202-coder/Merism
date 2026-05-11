"""Django signals for the conductor domain.

Loaded from :class:`merism.apps.MerismConfig.ready`. Keep this file
focused on signal handlers — the actual work lives in
:mod:`merism.conductor.tasks`.
"""

from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from merism.conductor.tasks import process_completed_session
from merism.models import InterviewSession

logger = logging.getLogger(__name__)


@receiver(post_save, sender=InterviewSession)
def _schedule_transcript_cleanup(
    sender,  # noqa: ARG001
    instance: InterviewSession,
    created: bool,  # noqa: ARG001
    update_fields: frozenset[str] | None = None,
    **kwargs,  # noqa: ANN003
) -> None:
    """Enqueue transcript cleanup when a session becomes ``completed``.

    Triggers on any save where the status is ``completed`` — the task
    itself is idempotent via ``has_clean_transcript``, so extra signal
    fires (e.g. when the voice consumer saves transcript + status in
    the same update) cost a task round-trip but don't corrupt data.
    """
    if instance.status != InterviewSession.Status.COMPLETED:
        return

    # If this save was a partial update_fields write that didn't touch
    # status, skip — avoids firing on every transcript-only update.
    if update_fields is not None and "status" not in update_fields:
        return

    try:
        process_completed_session.delay(str(instance.id))
    except Exception:  # noqa: BLE001 — broker unavailable shouldn't break saves
        logger.exception(
            "conductor.signal.enqueue_failed",
            extra={"session_id": str(instance.id)},
        )
