"""Custom report models — user-created AI research reports.

Reports are user-initiated, question-by-question analyses of completed
interview data. Unlike Insights (auto-generated), Reports let users
ask new research questions and get per-question AI analysis.

Three models:
- :class:`CustomReport` — the report container
- :class:`ReportSegment` — a labelled participant subset for filtering
- :class:`ReportQuestion` — a single question with AI-generated analysis
"""

from __future__ import annotations

import secrets
import uuid

from django.conf import settings
from django.db import models

from merism.models.study import Study
from merism.models.team import Team, TimestampedModel


def _generate_share_token() -> str:
    return secrets.token_urlsafe(32)


class CustomReport(TimestampedModel):
    """A user-created AI research report.

    Contains multiple questions, each with independent AI analysis.
    Supports segments (participant subsets), export, and public sharing.
    """

    class Status(models.TextChoices):
        DRAFT = "draft"
        GENERATING = "generating"
        READY = "ready"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="custom_reports")
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="custom_reports")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="merism_custom_reports",
    )
    title = models.CharField(max_length=300)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)

    # AI synthesis across all questions
    ai_synthesis = models.TextField(blank=True, default="")

    # Public share
    share_token = models.CharField(max_length=64, unique=True, default=_generate_share_token, db_index=True)
    is_public = models.BooleanField(default=False)

    generated_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")

    class Meta:
        db_table = "merism_custom_report"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["team", "study"], name="merism_cr_team_study_idx"),
            models.Index(fields=["share_token"], name="merism_cr_share_idx"),
        ]

    def __str__(self) -> str:
        return f"CustomReport({self.title[:40]})"

    @property
    def share_url(self) -> str:
        return f"/shared/report/{self.share_token}"


class ReportSegment(TimestampedModel):
    """A labelled participant subset for filtering report analysis."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="report_segments")
    report = models.ForeignKey(CustomReport, on_delete=models.CASCADE, related_name="segments")
    name = models.CharField(max_length=120)
    # Filter rule — same shape as CohortSegment.selector
    selector = models.JSONField(default=dict)
    participation_ids = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "merism_report_segment"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["report"], name="merism_rs_report_idx"),
        ]

    def __str__(self) -> str:
        return f"ReportSegment({self.name})"


class ReportQuestion(TimestampedModel):
    """A single question in a custom report with AI-generated analysis.

    Each question gets independent analysis: summary, chart, themes,
    and supporting quotes.
    """

    class QuestionType(models.TextChoices):
        OPEN_ENDED = "open_ended", "Open-ended question"
        MULTI_SELECT = "multi_select", "Multi-select question"
        SINGLE_SELECT = "single_select", "Single-select question"
        RATING = "rating", "Rating question"
        RANKING = "ranking", "Ranking question"

    class Status(models.TextChoices):
        PENDING = "pending"
        GENERATING = "generating"
        READY = "ready"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="report_questions")
    report = models.ForeignKey(CustomReport, on_delete=models.CASCADE, related_name="questions")
    question_number = models.PositiveIntegerField(default=1)
    title = models.TextField()
    question_type = models.CharField(max_length=20, choices=QuestionType.choices, default=QuestionType.OPEN_ENDED)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)

    # AI-generated analysis
    ai_summary = models.TextField(blank=True, default="")
    chart_spec = models.JSONField(default=dict, blank=True)
    themes = models.JSONField(default=list, blank=True)
    quotes = models.JSONField(default=list, blank=True)

    # Optional segment-specific analysis
    segment = models.ForeignKey(
        ReportSegment, on_delete=models.SET_NULL, null=True, blank=True, related_name="questions"
    )

    class Meta:
        db_table = "merism_report_question"
        ordering = ["question_number"]
        indexes = [
            models.Index(fields=["report", "question_number"], name="merism_rq_order_idx"),
        ]

    def __str__(self) -> str:
        return f"ReportQuestion(Q{self.question_number}: {self.title[:40]})"
