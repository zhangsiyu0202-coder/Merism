"""Stimulus (image/video/text/pdf/link) and Screener models.

Per ``merism-platform`` Req 3 (Screener) + Req 6 (Stimuli):
- Screener holds screening questions + pass logic; failing = polite drop.
- Stimulus is study-wide content (file or link), attachable to one or more
  guide questions.
"""

from __future__ import annotations

import uuid

from django.db import models

from merism.models.study import Study
from merism.models.team import Team, TimestampedModel


class Screener(TimestampedModel):
    """Screening questionnaire shown between Consent and the interview room.

    ``questions`` is a list of ``{id, text, type, options}`` dicts.
    ``pass_logic`` describes which answer combinations qualify the
    participant (inclusive by default).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="screeners")
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="screeners")
    questions = models.JSONField(default=list, blank=True)
    pass_logic = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "merism_screener"
        indexes = [
            models.Index(fields=["team", "study"], name="merism_scr_team_study_idx"),
        ]

    def __str__(self) -> str:
        q_count = len(self.questions) if isinstance(self.questions, list) else 0
        return f"Screener({q_count}Q, study={self.study_id})"


class Stimulus(TimestampedModel):
    """Content shown to a participant during specific guide questions.

    ``kind`` enumerates the supported media types. ``content`` holds the
    shape-specific payload (``url`` / ``text`` / ``title`` / ``description``).
    """

    class Kind(models.TextChoices):
        IMAGE = "image"
        VIDEO = "video"
        TEXT = "text"
        PDF = "pdf"
        LINK = "link"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="stimuli")
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="stimuli")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    title = models.CharField(max_length=200, blank=True, default="")
    description = models.TextField(blank=True, default="")
    content = models.JSONField(default=dict, blank=True)
    # IDs of Guide questions this stimulus is linked to (stored in guide JSON).
    linked_question_ids = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "merism_stimulus"
        indexes = [
            models.Index(fields=["team", "study"], name="merism_stim_team_study_idx"),
            models.Index(fields=["kind"], name="merism_stim_kind_idx"),
        ]

    def __str__(self) -> str:
        return f"Stimulus({self.kind}, {self.title or 'untitled'})"
