"""ConceptBlock & Concept — Concept Testing 2.0 (PRODUCT.md §3.4 extension).

A ``ConceptBlock`` groups N concept variants (each pointing at one
:class:`Stimulus`) that are shown side-by-side within a single session.
The AI moderator runs the same per-concept guide section once per
concept, with the rotation strategy controlling the order in which the
participant sees them.

Design decisions (see ADR 0007 if it lands):
- Per-block rotation: a study can own multiple independent comparison
  sets (e.g., package designs vs. ad copy).
- Rotation strategies: ``fixed`` / ``random_per_session`` /
  ``latin_square`` — the latter two implemented in
  :mod:`merism.concept.rotation`.
- Participants see "Concept 1 of 3" (numeric progress, no letter
  label) — labels are internal-only for AI prompts and reports.
"""

from __future__ import annotations

import uuid

from django.db import models

from merism.models.stimulus import Stimulus
from merism.models.study import Study
from merism.models.team import Team, TimestampedModel


class ConceptBlock(TimestampedModel):
    """A group of concepts tested side-by-side within one study."""

    class Rotation(models.TextChoices):
        FIXED = "fixed", "Fixed order (A → B → C)"
        RANDOM = "random_per_session", "Random per session"
        LATIN_SQUARE = "latin_square", "Latin-square balanced"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="concept_blocks")
    study = models.ForeignKey(
        Study, on_delete=models.CASCADE, related_name="concept_blocks"
    )
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    rotation = models.CharField(
        max_length=24,
        choices=Rotation.choices,
        default=Rotation.RANDOM,
    )
    show_counter_chip = models.BooleanField(
        default=True,
        help_text="Render the 'Concept N of M' chip in the room.",
    )

    class Meta:
        db_table = "merism_concept_block"
        indexes = [
            models.Index(fields=["team", "study"], name="merism_cblk_team_study_idx"),
        ]
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"ConceptBlock({self.title}, study={self.study_id})"


class Concept(TimestampedModel):
    """A single concept variant within a :class:`ConceptBlock`.

    ``label`` (e.g., "Concept A") is internal-only — shown to the AI
    moderator and research-facing reports, never to participants.
    ``rank`` is the baseline order for ``Rotation.FIXED`` and the seed
    for ``Rotation.LATIN_SQUARE``.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    block = models.ForeignKey(
        ConceptBlock, on_delete=models.CASCADE, related_name="concepts"
    )
    stimulus = models.ForeignKey(Stimulus, on_delete=models.CASCADE)
    label = models.CharField(max_length=40)
    rank = models.PositiveSmallIntegerField()
    notes = models.TextField(
        blank=True,
        default="",
        help_text="Research brief injected into the AI moderator prompt.",
    )

    class Meta:
        db_table = "merism_concept"
        ordering = ["rank"]
        unique_together = [("block", "rank")]

    def __str__(self) -> str:
        return f"Concept({self.label}, block={self.block_id})"


class ConceptRotationCursor(TimestampedModel):
    """Persistent rotation position for a :class:`ConceptBlock`.

    Used by ``Rotation.LATIN_SQUARE`` to coordinate concept ordering
    **across** sessions — every new participation advances the counter
    atomically, so over N participations every concept appears in
    every position exactly N/|concepts| times. A full Williams balanced
    design is overkill for MVP; a cyclic Latin square (row i =
    ``concepts shifted by i``) gives first-order balance.

    One row per block; created lazily on first participation.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    block = models.OneToOneField(
        ConceptBlock, on_delete=models.CASCADE, related_name="rotation_cursor"
    )
    position = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "merism_concept_rotation_cursor"

    def __str__(self) -> str:
        return f"ConceptRotationCursor(block={self.block_id}, pos={self.position})"
