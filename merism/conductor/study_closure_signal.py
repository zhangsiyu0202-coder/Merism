"""Study-level auto-close hook.

When a :class:`Participation` transitions to ``COMPLETED``, check whether
the study has hit its ``target_completed_count``. If so, flip the Study
status to ``CLOSED`` and mark every active StudyLink inactive so new
participants hit ``link_closed`` at ``/i/<slug>/``.

Single transaction, idempotent. Safe under concurrent signal fires via
``select_for_update`` on the Study row.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from merism.models import Participation, Study, StudyLink

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Participation)
def _close_study_when_target_reached(
    sender,  # noqa: ARG001
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
                StudyLink.objects.filter(study=study, is_active=True).update(
                    is_active=False
                )
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
