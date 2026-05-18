"""Auto-index transcript when a session completes."""

from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from merism.models import InterviewSession


@receiver(post_save, sender=InterviewSession)
def trigger_transcript_index(sender, instance: InterviewSession, **kwargs) -> None:
    """Queue transcript indexing when session status becomes completed."""
    if instance.status != "completed":
        return
    if not instance.transcript:
        return

    from merism.knowledge.tasks import index_transcript_task

    index_transcript_task.delay(str(instance.id))
