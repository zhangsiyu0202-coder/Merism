"""Study-level auto-close hook.

When a :class:`Participation` transitions to ``COMPLETED``, check whether
the study has hit its ``target_completed_count``. If so, flip the Study
status to ``CLOSED`` so the inbox + analytics surfaces show the study as
closed.

Per the 2026-05-23 access-control simplification, this signal does
**not** flip ``StudyLink.is_active``. The "accepting responses" toggle
is researcher-controlled — automatic closure is metadata only. If a
researcher wants to fully stop participation, they flip ``is_active``
off in the Recruit tab.

Single transaction, idempotent. Safe under concurrent signal fires via
``select_for_update`` on the Study row.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from merism.models import Participation, Study

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Participation)
def _close_study_when_target_reached(
    sender,
    instance: Participation,
    update_fields=None,
    **kwargs,
) -> None:
    if instance.status != Participation.Status.COMPLETED:
        return
    if update_fields is not None and "status" not in update_fields:
        return

    try:
        with transaction.atomic():
            study = Study.objects.select_for_update().get(id=instance.study_id)
            if study.status == Study.Status.CLOSED:
                return
            if study.actual_completed_count >= study.target_completed_count:
                study.status = Study.Status.CLOSED
                study.save(update_fields=["status", "updated_at"])
                logger.info(
                    "study.auto_closed_on_target",
                    extra={
                        "study_id": str(study.id),
                        "target": study.target_completed_count,
                    },
                )
    except Exception:
        logger.exception(
            "study.auto_close_failed",
            extra={"study_id": str(instance.study_id)},
        )
