"""Codebook governance models.

Three models that track codebook evolution across a study:

- :class:`CodebookVersion` — immutable snapshot of the full codebook at a point in time.
- :class:`CodeChange` — a single proposed or applied change (add/merge/split/rename/deprecate).
- :class:`CodeMapping` — old→new code_id mapping for retagging affected quotes.
"""

from __future__ import annotations

import uuid

from django.db import models

from merism.models.study import Study
from merism.models.team import Team, TimestampedModel


class CodebookVersion(TimestampedModel):
    """Immutable snapshot of a study's codebook at a specific version."""

    class Source(models.TextChoices):
        SEED = "seed"
        REVIEW = "review"
        MANUAL = "manual"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="codebook_versions")
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="codebook_versions")
    version = models.PositiveIntegerField()
    codes = models.JSONField(
        default=list,
        help_text="Immutable snapshot: [{code_id, name, description, parent_id, status, source}]",
    )
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.REVIEW)

    class Meta:
        db_table = "merism_codebook_version"
        unique_together = [("study", "version")]
        ordering = ["-version"]
        indexes = [
            models.Index(fields=["study", "-version"], name="merism_cbv_study_ver_idx"),
        ]

    def __str__(self) -> str:
        return f"CodebookVersion(study={self.study_id}, v{self.version})"


class CodeChange(TimestampedModel):
    """A single codebook change proposal or applied operation."""

    class ChangeType(models.TextChoices):
        ADD = "add"
        MERGE = "merge"
        SPLIT = "split"
        RENAME = "rename"
        DEPRECATE = "deprecate"

    class Status(models.TextChoices):
        PROPOSED = "proposed"
        APPROVED = "approved"
        REJECTED = "rejected"
        APPLIED = "applied"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="code_changes")
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="code_changes")
    from_version = models.ForeignKey(
        CodebookVersion, on_delete=models.CASCADE, related_name="changes_from"
    )
    to_version = models.ForeignKey(
        CodebookVersion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="changes_to",
    )
    change_type = models.CharField(max_length=16, choices=ChangeType.choices)
    payload = models.JSONField(default=dict)
    rationale = models.TextField(blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PROPOSED)
    session = models.ForeignKey(
        "merism.InterviewSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="code_changes",
        help_text="Session that triggered this change (if from pipeline).",
    )

    class Meta:
        db_table = "merism_code_change"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["study", "status"], name="merism_cc_study_status_idx"),
            models.Index(fields=["study", "change_type"], name="merism_cc_study_type_idx"),
        ]

    def __str__(self) -> str:
        return f"CodeChange({self.change_type}, {self.status})"


class CodeMapping(TimestampedModel):
    """Maps an old code_id to a new code_id after a codebook change.

    Used by RetaggingJob to find and update affected quotes.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="code_mappings")
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="code_mappings")
    change = models.ForeignKey(CodeChange, on_delete=models.CASCADE, related_name="mappings")
    old_code_id = models.CharField(max_length=64)
    new_code_id = models.CharField(max_length=64, blank=True, default="")
    version = models.ForeignKey(
        CodebookVersion, on_delete=models.CASCADE, related_name="mappings"
    )

    class Meta:
        db_table = "merism_code_mapping"
        indexes = [
            models.Index(fields=["study", "old_code_id"], name="merism_cm_study_old_idx"),
        ]

    def __str__(self) -> str:
        return f"CodeMapping({self.old_code_id} → {self.new_code_id or '∅'})"
