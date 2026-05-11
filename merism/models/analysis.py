"""Analysis models — cross-session pattern detection.

Three models that answer "why?" across an entire study:

- :class:`StudyGoal` — a concrete question the study aims to answer,
  upgraded from the free-text ``Study.research_objectives`` list so
  coverage can be measured per-goal.
- :class:`Theme` — a cluster of semantically-similar quotes across
  sessions (different participants, same recurring idea).
- :class:`CoverageSnapshot` — a point-in-time measurement of how well
  each StudyGoal has been covered by the completed sessions.
- :class:`CohortSegment` — a labelled subset of participations
  (e.g. "power users", "new users") used for A/B comparison of themes.
"""

from __future__ import annotations

import uuid

from django.db import models

try:
    from pgvector.django import VectorField
except ImportError:  # pragma: no cover — dev-only fallback
    VectorField = None  # type: ignore[assignment,misc]

from merism.models.knowledge import EMBEDDING_DIM
from merism.models.study import Study
from merism.models.team import Team, TimestampedModel


class StudyGoal(TimestampedModel):
    """A concrete research question the study aims to answer.

    Replaces the free-text ``Study.research_objectives`` list with a
    proper model so we can measure coverage per goal and steer the
    moderator toward under-covered goals.
    """

    class Priority(models.TextChoices):
        P0 = "P0", "Must answer"
        P1 = "P1", "Should answer"
        P2 = "P2", "Nice to answer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="study_goals")
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="goals")
    text = models.TextField(help_text="The research question as a natural-language prompt.")
    priority = models.CharField(max_length=4, choices=Priority.choices, default=Priority.P1)
    display_order = models.PositiveIntegerField(default=0)
    # 0.0-1.0. Updated by ``merism.analysis.coverage.goal_coverage`` each
    # time a session completes. Stored so we can compute without aggregating
    # every query.
    coverage = models.FloatField(default=0.0)
    is_answered = models.BooleanField(default=False)

    class Meta:
        db_table = "merism_study_goal"
        ordering = ["study", "display_order"]
        indexes = [
            models.Index(fields=["study", "display_order"], name="merism_sg_study_order_idx"),
            models.Index(fields=["team", "priority"], name="merism_sg_team_prio_idx"),
        ]

    def __str__(self) -> str:
        return f"StudyGoal({self.priority}, {self.text[:40]}…)"


class Theme(TimestampedModel):
    """A cluster of semantically-similar quotes across sessions.

    Produced by ``merism.analysis.themes`` — the clusterer groups quote
    embeddings via HDBSCAN, then the summarizer names each cluster.

    ``centroid_embedding`` enables incremental assignment: when a new
    quote arrives post-hoc, we can compute cosine similarity to all
    theme centroids and assign it to the closest one above threshold.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft (auto-generated)"
        CONFIRMED = "confirmed", "Confirmed by researcher"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="themes")
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="themes")
    # Short human-readable label, e.g. "Pricing too high"
    name = models.CharField(max_length=200)
    # 1-2 sentence description of what unites the quotes in this theme
    description = models.TextField(blank=True, default="")
    # Representative quote IDs (top-3 closest to centroid)
    representative_quote_ids = models.JSONField(default=list, blank=True)
    # All session IDs that contributed at least one quote to this theme
    session_ids = models.JSONField(default=list, blank=True)
    # Denormalised counts for fast listing
    session_count = models.PositiveIntegerField(default=0)
    quote_count = models.PositiveIntegerField(default=0)
    # Sentiment distribution across quotes in this theme
    # Shape: {"positive": int, "negative": int, "neutral": int, "mixed": int}
    sentiment_mix = models.JSONField(default=dict, blank=True)
    # Centroid for incremental assignment. May be null for themes created
    # manually by researchers.
    centroid_embedding = (
        VectorField(dimensions=EMBEDDING_DIM, null=True, blank=True)
        if VectorField is not None
        else models.JSONField(default=list, blank=True)
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)

    class Meta:
        db_table = "merism_theme"
        ordering = ["-session_count", "-created_at"]
        indexes = [
            models.Index(fields=["team", "study"], name="merism_theme_team_study_idx"),
            models.Index(fields=["status"], name="merism_theme_status_idx"),
        ]

    def __str__(self) -> str:
        return f"Theme({self.name} · {self.session_count} sessions)"


class CoverageSnapshot(TimestampedModel):
    """Point-in-time measurement of how well the study's goals are covered.

    Rebuilt after every session completion. ``goal_coverage`` is the
    per-goal ratio (0.0-1.0); ``overall_coverage`` is the priority-weighted
    average.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="coverage_snapshots")
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="coverage_snapshots")
    # {goal_id: 0.0..1.0}
    goal_coverage = models.JSONField(default=dict, blank=True)
    overall_coverage = models.FloatField(default=0.0)
    # Goals with coverage < threshold — what the researcher should chase
    gaps = models.JSONField(default=list, blank=True)
    # How many completed sessions this snapshot was built from
    session_count = models.PositiveIntegerField(default=0)
    # Notes from the gap detector (human-readable recommendations)
    recommendations = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "merism_coverage_snapshot"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["team", "study"], name="merism_cov_team_study_idx"),
            models.Index(fields=["study", "-created_at"], name="merism_cov_recent_idx"),
        ]

    def __str__(self) -> str:
        return f"CoverageSnapshot(study={self.study_id}, overall={self.overall_coverage:.0%})"


class CohortSegment(TimestampedModel):
    """A labelled subset of participations for A/B theme comparison.

    Example: a researcher defines "power_users" (participants with >2 years
    product usage) and "new_users" (<3 months). The analysis layer can then
    compare theme distributions across the two segments.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="cohort_segments")
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="cohort_segments")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    # Rule that selects participations.
    # Shape: {"type": "screener_answer", "question_id": "usage_duration",
    #         "match": {"op": ">=", "value": 2}}
    # or:    {"type": "tag", "tag": "power_user"}
    # or:    {"type": "manual", "participation_ids": [...]}
    selector = models.JSONField(default=dict)
    # Cached participation IDs (rebuilt when selector changes)
    participation_ids = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "merism_cohort_segment"
        ordering = ["study", "name"]
        indexes = [
            models.Index(fields=["team", "study"], name="merism_cohort_team_study_idx"),
        ]

    def __str__(self) -> str:
        return f"CohortSegment({self.name})"
