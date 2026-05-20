"""Auto-create a primary StudyLink whenever a Study is created.

Per the 2026-05-20 simplification: a Study has exactly one canonical
share URL, surfaced as ``Study.primary_link``. Researchers don't manage
multiple links — that complexity stays in the data model (broadcast /
invitation flows still create derived per-recipient tokens) but is
hidden from the UI.

This signal runs on ``post_save(Study, created=True)`` and uses
``get_or_create`` so re-saving a Study row does nothing. The unique
constraint ``merism_studylink_one_primary_per_study`` is the safety
net: even if two workers race the create, only one wins.

The auto-created link defaults to ``link_mode=NAMED`` so the participant
flow shows the name + contact form before consent. Researchers can
flip it to anonymous through Django admin if needed.
"""

from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from merism.models import Study, StudyLink

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Study, dispatch_uid="merism.study_primary_link.ensure")
def ensure_primary_link(sender, instance: Study, created: bool, **kwargs) -> None:
    """Create the primary link when a Study is created.

    Idempotent: re-saving an existing Study does nothing.
    Safe under concurrent creates: ``UniqueConstraint`` means only one
    primary survives the race.
    """
    if not created:
        return

    # Already has one (e.g. fixture / test factory created it explicitly)?
    if StudyLink.objects.filter(study=instance, is_primary=True).exists():
        return

    try:
        StudyLink.objects.create(
            study=instance,
            team=instance.team,
            is_primary=True,
            is_active=True,
            link_mode=StudyLink.LinkMode.NAMED,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "study.primary_link.create_failed",
            extra={"study_id": str(instance.id), "error": str(exc)},
        )
