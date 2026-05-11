"""Report-domain models.

Per ``merism-platform`` Req 16-19:
- ``SessionInsight``      — per-session AI-generated analysis.
- ``AggregateSynthesis``  — interim study-wide rollup.
- ``StudyReport``         — final structured report with block schema
                           (text / metric / quote / chart).
- ``CustomReportQuery``   — sidebar Q&A, or cross-study Knowledge Explore Q&A.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from merism.models.interview import InterviewSession
from merism.models.study import Study
from merism.models.team import Team, TimestampedModel


class SessionInsight(TimestampedModel):
    """Per-session analysis generated after ``InterviewSession`` completes.

    Shape per Req 16.4:
      - ``summary``: 3-5 sentence summary
      - ``highlights``: [{text, ts_start, ts_end, importance}]
      - ``tags``: {dimension_name: value} — AI-derived dimensions
      - ``extracted_tasks``: [{title, category, priority, evidence_quote_id}]
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="session_insights")
    session = models.OneToOneField(
        InterviewSession,
        on_delete=models.CASCADE,
        related_name="insight",
    )
    summary = models.TextField(blank=True, default="")
    highlights = models.JSONField(default=list, blank=True)
    tags = models.JSONField(default=dict, blank=True)
    extracted_tasks = models.JSONField(default=list, blank=True)

    trace_id = models.UUIDField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "merism_session_insight"
        indexes = [
            models.Index(fields=["team"], name="merism_si_team_idx"),
        ]

    def __str__(self) -> str:
        return f"SessionInsight(session={self.session_id})"


class AggregateSynthesis(TimestampedModel):
    """Interim aggregate rollup — lighter than a full StudyReport, updated
    incrementally as sessions complete."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="aggregate_syntheses")
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="aggregate_syntheses")
    headline = models.TextField(blank=True, default="")
    themes = models.JSONField(default=list, blank=True)
    covered_goals = models.JSONField(default=list, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "merism_aggregate_synthesis"
        indexes = [
            models.Index(fields=["team", "study", "-generated_at"], name="merism_as_recent_idx"),
        ]

    def __str__(self) -> str:
        return f"AggregateSynthesis(study={self.study_id})"


class StudyReport(TimestampedModel):
    """Final study report — structured into four panels.

    Per ``PRODUCT.md`` §4 and ``merism-platform`` Req 17:

    - ``content``: ``{exec_summary, quant_panel, qual_panel, insight_nuggets}``
      each panel holds domain-typed blocks (text / metric / quote / chart).
      The lower-level block schema lives in :mod:`merism.reports.schema`
      (Pydantic v2 validator).
    - ``charts``: a flat JSON list of every chart_spec used by the report
      so the UI can render without re-running analysis.
    """

    class Status(models.TextChoices):
        DRAFT = "draft"
        GENERATING = "generating"
        READY = "ready"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="study_reports")
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="reports")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    # Structured 4-panel content (see docstring). Validated by
    # merism.reports.schema.StudyReportContent (Pydantic v2).
    content = models.JSONField(default=dict, blank=True)
    # Flat list of chart_specs ({type, title, x, y, unit, ...}).
    charts = models.JSONField(default=list, blank=True)
    generated_by = models.CharField(max_length=64, blank=True, default="")
    generated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "merism_study_report"
        indexes = [
            models.Index(fields=["team", "study"], name="merism_sr_team_study_idx"),
            models.Index(fields=["status"], name="merism_sr_status_idx"),
        ]

    def __str__(self) -> str:
        return f"StudyReport(study={self.study_id}, {self.status})"


class CustomReportQuery(TimestampedModel):
    """A single Q&A in the Custom Report sidebar or Knowledge Explore.

    ``study`` may be NULL for cross-study Knowledge Explore questions.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="custom_report_queries")
    study = models.ForeignKey(
        Study,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="custom_report_queries",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="merism_custom_report_queries",
    )
    question = models.TextField()
    answer_markdown = models.TextField(blank=True, default="")
    chart_spec = models.JSONField(default=dict, blank=True)
    citations = models.JSONField(default=list, blank=True)
    pinned = models.BooleanField(default=False)

    class Meta:
        db_table = "merism_custom_report_query"
        indexes = [
            models.Index(fields=["team", "study", "-created_at"], name="merism_crq_recent_idx"),
            models.Index(fields=["pinned"], name="merism_crq_pinned_idx"),
        ]

    def __str__(self) -> str:
        return f"CustomReportQuery({self.question[:40]})"
