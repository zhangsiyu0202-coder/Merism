"""Glossary model — team/study-level term list for ASR correction.

Each entry maps one or more ASR-likely misrecognitions to a canonical
term. Applied in ``stage1_asr_correct`` before any LLM-based cleaning.

Example:
    canonical: "Merism"
    variants:  ["米瑞姆", "merism", "me mism"]
"""

from __future__ import annotations

import uuid

from django.db import models

from merism.models.study import Study
from merism.models.team import Team, TimestampedModel


class Glossary(TimestampedModel):
    """A set of term replacements for ASR / transcript normalization."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="glossaries")
    # If study is null → team-wide glossary (applies to all studies in team)
    study = models.ForeignKey(
        Study, on_delete=models.CASCADE, null=True, blank=True,
        related_name="glossaries",
    )
    canonical = models.CharField(max_length=200, help_text="The correct spelling")
    variants = models.JSONField(
        default=list,
        help_text='List of known misrecognitions, e.g. ["米瑞姆", "merism"]',
    )
    # Case-insensitive match when True
    case_insensitive = models.BooleanField(default=True)

    class Meta:
        db_table = "merism_glossary"
        indexes = [
            models.Index(fields=["team", "study"], name="merism_gloss_team_study_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["team", "study", "canonical"],
                name="merism_gloss_unique_canonical",
            ),
        ]

    def __str__(self) -> str:
        return f"Glossary({self.canonical})"
