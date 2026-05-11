"""Signal handlers that write InboxItem rows on lifecycle events.

Wired from :class:`merism.apps.MerismConfig.ready`.

Dedup is enforced at the DB (unique_together on ``(team, kind, ref_kind,
ref_id)``). Second-fire signals silently no-op via
``get_or_create`` — no caller-visible error.
"""

from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from merism.models import InboxItem, InterviewSession, SessionInsight, Study

logger = logging.getLogger(__name__)


@receiver(post_save, sender=InterviewSession)
def _on_session_completed(
    sender,  # noqa: ARG001
    instance: InterviewSession,
    update_fields=None,
    **kwargs,
) -> None:
    if instance.status != InterviewSession.Status.COMPLETED:
        return
    if update_fields is not None and "status" not in update_fields:
        return
    try:
        InboxItem.objects.get_or_create(
            team=instance.team,
            kind=InboxItem.Kind.SESSION_COMPLETED,
            ref_kind="session",
            ref_id=str(instance.id),
            defaults={
                "title": f"Session completed · {_study_label(instance.study)}",
                "body": "Transcript is processing; insights will arrive shortly.",
                "payload": {
                    "study_id": str(instance.study_id),
                    "session_id": str(instance.id),
                    "mode": instance.mode,
                },
                "trace_id": instance.trace_id,
            },
        )
    except Exception:
        logger.exception("inbox.session_completed_write_failed")


@receiver(post_save, sender=SessionInsight)
def _on_insight_ready(
    sender,  # noqa: ARG001
    instance: SessionInsight,
    created: bool,
    **kwargs,
) -> None:
    if not created:
        return
    try:
        InboxItem.objects.get_or_create(
            team=instance.team,
            kind=InboxItem.Kind.INSIGHT_READY,
            ref_kind="insight",
            ref_id=str(instance.id),
            defaults={
                "title": f"Insight ready · {_study_label(instance.session.study)}",
                "body": (instance.summary or "")[:240],
                "payload": {
                    "study_id": str(instance.session.study_id),
                    "session_id": str(instance.session_id),
                    "insight_id": str(instance.id),
                },
                "trace_id": instance.trace_id,
            },
        )
    except Exception:
        logger.exception("inbox.insight_ready_write_failed")


@receiver(post_save, sender=Study)
def _on_study_closed(
    sender,  # noqa: ARG001
    instance: Study,
    update_fields=None,
    **kwargs,
) -> None:
    if instance.status != Study.Status.CLOSED:
        return
    if update_fields is not None and "status" not in update_fields:
        return
    try:
        InboxItem.objects.get_or_create(
            team=instance.team,
            kind=InboxItem.Kind.STUDY_COMPLETED,
            ref_kind="study",
            ref_id=str(instance.id),
            defaults={
                "title": f"Study closed · {_study_label(instance)}",
                "body": (
                    f"Target reached — {instance.actual_completed_count} "
                    f"of {instance.target_completed_count} sessions completed."
                ),
                "payload": {
                    "study_id": str(instance.id),
                    "completed": instance.actual_completed_count,
                    "target": instance.target_completed_count,
                },
            },
        )
    except Exception:
        logger.exception("inbox.study_completed_write_failed")


def _study_label(study: Study) -> str:
    return study.name or study.research_goal[:60]
