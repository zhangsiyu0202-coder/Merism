"""Study domain models.

Per ``merism-platform`` Req 1/2/7/21:
- ``Study.research_goal`` is a single ``TextField`` (not a multi-goal flat list).
- ``Study.status`` flows ``draft → ready → recruiting → active → closed → archived``.
- ``StudyLink`` is the slug-based public URL for receptivist access.
- ``StudyTemplate`` seeds the wizard; can be system-owned or team-owned.
- ``StudyTrigger`` fires behavior-based recruitment (per ADR 0001, runs in
  Celery beat not plugin-server).
"""

from __future__ import annotations

import secrets
import string
import uuid
from typing import Any

from django.conf import settings
from django.db import models

from merism.models.team import Team, TimestampedModel


def _generate_slug(length: int = 10) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class Study(TimestampedModel):
    """A single research study.

    The research goal is the North Star: every AI step (guide generation /
    outline review / moderator prompt / session analysis / report / custom
    Q&A) anchors on this one text field.
    """

    class Status(models.TextChoices):
        DRAFT = "draft"
        LIVE = "live"
        CLOSED = "closed"

    class InterviewMode(models.TextChoices):
        VOICE = "voice"
        VIDEO = "video"
        TEXT = "text"
        OFFLINE = "offline"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="studies")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="merism_studies_created",
    )

    # ── Canonical research goal (Rule 7 in AGENTS.md) ─────
    research_goal = models.TextField(help_text="The single research goal anchoring every AI step.")
    research_background = models.TextField(blank=True, default="")
    hypothesis = models.TextField(blank=True, default="")
    success_metrics = models.JSONField(default=dict, blank=True)

    # ── Structured research objectives (Project settings UX) ──
    # A numbered list of concrete questions the study aims to answer.
    # The single ``research_goal`` stays the North Star (one line) that
    # the AI anchors on; ``research_objectives`` are user-facing bullet
    # items shown as an OrderedList on the Settings tab.
    research_objectives = models.JSONField(
        default=list,
        blank=True,
        help_text='["Understand X...", "Map Y...", "Validate Z..."] — list of strings.',
    )

    # ── Codebook (qualitative coding taxonomy, Sprint 3) ─────
    # List of {code_id, name, description, examples, source}.
    # Seeded on first quote-processing pass from research_objectives,
    # then grown by the inductive tagger as new codes surface.
    codebook = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            '[{"code_id": "pricing_complaint", "name": "Pricing complaint", '
            '"description": "...", "examples": ["too expensive"], "source": '
            '"seeded" | "inductive" | "manual"}]'
        ),
    )

    # ── Recruitment plan (Phase 5 · Recruit tab) ─────────────
    # Free-text description of who the study wants to talk to.
    target_audience = models.TextField(blank=True, default="")
    # How many completed sessions is the study aiming for?
    target_completed_count = models.PositiveIntegerField(default=10)
    # Structured quota constraints. Shape:
    #   [{"dimension": "age", "label": "Age ranges", "segments": [
    #       {"label": "25-34", "target": 5}, {"label": "35-44", "target": 3}]}]
    recruitment_quotas = models.JSONField(default=list, blank=True)

    # ── Display ─────────────────────────────────────────────
    name = models.CharField(max_length=200, blank=True, default="")
    slug = models.SlugField(max_length=80, unique=True, null=True, blank=True)

    # ── Lifecycle ───────────────────────────────────────────
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    interview_mode = models.CharField(
        max_length=16,
        choices=InterviewMode.choices,
        default=InterviewMode.VOICE,
    )

    # ── Configuration ──────────────────────────────────────
    # Expected interview duration in minutes (hints guide generator + budget).
    estimated_minutes = models.PositiveIntegerField(default=20)
    # Section count heuristic (None = let AI decide from estimated_minutes).
    section_count_override = models.PositiveIntegerField(null=True, blank=True)
    # Voice barge-in (ADR 0002). When True, the participant can interrupt
    # the AI mid-sentence; cancels the current TTS + moderator stream.
    # Default off to preserve research data quality.
    barge_in_enabled = models.BooleanField(default=False)

    # ── Completion tracking (aggregate, not counter) ──
    # ``actual_completed_count`` is a **property**, not a stored field.
    # Storing a counter means maintaining a race-prone +1 on every
    # Participation completion. Using Participation.objects.filter().count()
    # as the source of truth is O(1) with the existing status index and
    # cannot drift. Admin/API that needs this value without N+1 should
    # prefetch via ``Study.objects.with_stats()``.

    @property
    def actual_completed_count(self) -> int:
        """Number of non-preview participations that have COMPLETED status."""
        return self.participations.filter(
            status="completed", is_preview=False
        ).count()

    @property
    def is_target_reached(self) -> bool:
        return self.actual_completed_count >= self.target_completed_count

    objects = models.Manager()  # canonical

    @classmethod
    def annotate_completed_count(cls, qs=None):
        """Return a queryset with ``actual_completed_count_annot`` annotated.

        Usage in admin/API:
            Study.annotate_completed_count().values("id", "actual_completed_count_annot")
        """
        from django.db.models import Count, Q
        qs = qs if qs is not None else cls.objects.all()
        return qs.annotate(
            actual_completed_count_annot=Count(
                "participations",
                filter=Q(participations__status="completed", participations__is_preview=False),
            )
        )


    class Meta:
        db_table = "merism_study"
        indexes = [
            models.Index(fields=["team", "status"], name="merism_study_team_status_idx"),
            models.Index(fields=["team", "-created_at"], name="merism_study_team_recent_idx"),
        ]

    def __str__(self) -> str:
        return f"Study({self.name or self.research_goal[:40]})"

    # ── Convenience state checks ───────────────────────────
    def is_draft(self) -> bool:
        return self.status == self.Status.DRAFT

    def is_active(self) -> bool:
        return self.status == self.Status.LIVE


class StudyLink(TimestampedModel):
    """Public slug URL a participant opens to join a study."""

    class LinkMode(models.TextChoices):
        ANONYMOUS = "anonymous", "不记名"
        NAMED = "named", "记名"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="links")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="study_links")
    slug = models.SlugField(max_length=16, unique=True, default=_generate_slug)
    link_mode = models.CharField(
        max_length=16,
        choices=LinkMode.choices,
        default=LinkMode.ANONYMOUS,
        help_text="anonymous=直接开始; named=需输入姓名/联系方式",
    )
    short_link_domain = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Custom short-link domain (e.g. 'go.acme.com'). Empty = use app domain.",
    )
    is_active = models.BooleanField(default=True)
    require_invitation = models.BooleanField(default=False, help_text="If True, /i/<slug>/ requires ?t=<token> from an Invitation row.")
    # Optional hard expiry. NULL = never expires. The /i/<slug> resolver
    # treats past expiries the same as ``is_active=False``.
    expires_at = models.DateTimeField(null=True, blank=True)

    # Click counter cache (updated atomically via F() on each recorded click).
    clicks = models.PositiveIntegerField(default=0)
    last_clicked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "merism_study_link"
        indexes = [
            models.Index(fields=["slug"], name="merism_link_slug_idx"),
        ]

    @property
    def url_path(self) -> str:
        return f"/i/{self.slug}"

    @property
    def full_url(self) -> str:
        """Full URL including domain. If short_link_domain is set, uses that."""
        if self.short_link_domain:
            return f"https://{self.short_link_domain}/i/{self.slug}"
        return f"/i/{self.slug}"

    def __str__(self) -> str:
        return f"StudyLink(/{self.slug})"


class StudyTemplate(TimestampedModel):
    """A seed template for the Study creation wizard.

    ``is_system=True`` templates are shipped by Merism (data migration seeds);
    ``is_system=False`` are team-owned user-created templates.
    """

    class Category(models.TextChoices):
        PRICING = "pricing"
        ONBOARDING = "onboarding"
        CHURN = "churn"
        CONCEPT_TEST = "concept_test"
        USABILITY = "usability"
        OTHER = "other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, null=True, blank=True, related_name="study_templates"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    category = models.CharField(max_length=32, choices=Category.choices, default=Category.OTHER)
    interview_mode = models.CharField(
        max_length=16,
        choices=Study.InterviewMode.choices,
        default=Study.InterviewMode.VOICE,
    )
    # Body of the template — a draft research_goal / guide structure / hints.
    payload = models.JSONField(default=dict)
    is_system = models.BooleanField(default=False)

    class Meta:
        db_table = "merism_study_template"
        indexes = [
            models.Index(fields=["team", "category"], name="merism_tmpl_team_cat_idx"),
            models.Index(fields=["is_system"], name="merism_tmpl_system_idx"),
        ]

    def __str__(self) -> str:
        return f"StudyTemplate({self.name})"


class StudyTrigger(TimestampedModel):
    """Behavior-based recruitment trigger. Fires a broadcast when a matching
    event is ingested (evaluation runs in Celery beat per ADR 0001)."""

    class ConditionType(models.TextChoices):
        EVENT = "event"
        SEGMENT = "segment"
        COHORT = "cohort"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="study_triggers")
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="triggers")
    condition_type = models.CharField(
        max_length=16, choices=ConditionType.choices, default=ConditionType.EVENT
    )
    event_name = models.CharField(max_length=200, blank=True, default="")
    predicate = models.JSONField(
        default=dict,
        blank=True,
        help_text="Condition-specific filter. Event → {properties: [...]}.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "merism_study_trigger"
        indexes = [
            models.Index(fields=["team", "is_active"], name="merism_trig_team_active_idx"),
            models.Index(fields=["study"], name="merism_trig_study_idx"),
        ]

    def __str__(self) -> str:
        return f"StudyTrigger({self.event_name or self.condition_type})"
