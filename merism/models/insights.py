"""Insights models — auto-generated research findings.

Insights are system-generated based on the study's research goal,
interview guide, and completed sessions. They represent the AI's
standardized comprehensive analysis of the entire research project.

Three models:
- :class:`StudyInsights` — top-level container (one per study)
- :class:`InsightHighlight` — 3-6 core high-level findings
- :class:`InsightFinding` — deep expandable research conclusions
"""

from __future__ import annotations

import uuid

from django.db import models

from merism.models.study import Study
from merism.models.team import Team, TimestampedModel


class StudyInsights(TimestampedModel):
    """Top-level insights container for a study.

    One per study. Holds the executive summary metadata and generation
    status. Highlights and findings are child models.
    """

    class Status(models.TextChoices):
        PENDING = "pending"
        GENERATING = "generating"
        READY = "ready"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="study_insights")
    study = models.OneToOneField(Study, on_delete=models.CASCADE, related_name="insights")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)

    # Executive summary metadata
    completed_interviews = models.PositiveIntegerField(default=0)
    avg_session_minutes = models.FloatField(default=0.0)
    interview_topics = models.JSONField(default=list, blank=True)
    executive_summary = models.TextField(blank=True, default="")

    generated_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")

    class Meta:
        db_table = "merism_study_insights"
        indexes = [
            models.Index(fields=["team", "study"], name="merism_si2_team_study_idx"),
        ]

    def __str__(self) -> str:
        return f"StudyInsights(study={self.study_id}, {self.status})"


class InsightHighlight(TimestampedModel):
    """A core high-level insight (3-6 per study).

    Highlights are the AI's top-level takeaways — short, scannable,
    and optionally linked to a deeper finding.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="insight_highlights")
    insights = models.ForeignKey(StudyInsights, on_delete=models.CASCADE, related_name="highlights")
    headline = models.CharField(max_length=200)
    summary = models.TextField(blank=True, default="")
    icon = models.CharField(max_length=50, blank=True, default="")
    display_order = models.PositiveIntegerField(default=0)
    # Optional link to a deeper finding
    linked_finding = models.ForeignKey(
        "InsightFinding", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        db_table = "merism_insight_highlight"
        ordering = ["display_order"]
        indexes = [
            models.Index(fields=["insights", "display_order"], name="merism_ih_order_idx"),
        ]

    def __str__(self) -> str:
        return f"InsightHighlight({self.headline[:40]})"


class InsightFinding(TimestampedModel):
    """A deep research finding with full analysis.

    Findings are the expandable accordion rows. Each contains a chart,
    theme breakdown, subthemes, insight nuggets, and supporting evidence.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="insight_findings")
    insights = models.ForeignKey(StudyInsights, on_delete=models.CASCADE, related_name="findings")
    title = models.CharField(max_length=300)
    summary = models.TextField(blank=True, default="")
    display_order = models.PositiveIntegerField(default=0)

    # Expanded content (JSON structures)
    chart_spec = models.JSONField(default=dict, blank=True)
    chart_interpretation = models.TextField(blank=True, default="")
    themes = models.JSONField(default=list, blank=True)
    subthemes = models.JSONField(default=list, blank=True)
    insight_nuggets = models.JSONField(default=list, blank=True)
    supporting_evidence = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "merism_insight_finding"
        ordering = ["display_order"]
        indexes = [
            models.Index(fields=["insights", "display_order"], name="merism_if_order_idx"),
        ]

    def __str__(self) -> str:
        return f"InsightFinding({self.title[:40]})"
