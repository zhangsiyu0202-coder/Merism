"""Merism Django admin registrations.

Django's built-in admin (``django.contrib.admin``) is already installed
and mounted at ``/admin/``. This file tells that engine WHICH Merism
models to expose and HOW to display each one. No new admin "system" is
introduced here — we're configuring the one Django ships.

django-unfold provides a modern skin on top of the stock admin; we
inherit from :class:`unfold.admin.ModelAdmin` so our registrations pick
up the unfold look while remaining 100% compatible with Django admin
conventions.

The admin home page is augmented with a KPI dashboard via the UNFOLD
``DASHBOARD_CALLBACK`` (see :func:`dashboard_callback` below). This
replaces the standalone ``/platform/`` SPA.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.contrib import admin
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from unfold.admin import ModelAdmin

admin.site.site_header = "Merism 管理后台"
admin.site.site_title = "Merism 管理"
admin.site.index_title = "平台管理"

from merism.models import (
    AggregateSynthesis,
    ChannelConfig,
    ChannelHealthCheck,
    ChannelTarget,
    Concept,
    ConceptBlock,
    CustomReportQuery,
    DeliveryRecord,
    InterviewGuide,
    InterviewRecording,
    InterviewSession,
    Invitation,
    InboxItem,
    LinkClick,
    LinkShareEvent,
    SessionEvent,
    KnowledgeChunk,
    KnowledgeDocument,
    MessageTemplate,
    Organization,
    OrganizationMembership,
    Participant,
    Participation,
    RecruitmentBroadcast,
    Screener,
    SessionInsight,
    SessionQuote,
    Stimulus,
    Study,
    StudyLink,
    StudyReport,
    StudyTemplate,
    StudyTrigger,
    Team,
)


# ── Tenancy ──────────────────────────────────────────────


@admin.register(Organization)
class OrganizationAdmin(ModelAdmin):
    list_display = ("name", "slug", "team_count_", "created_at")
    search_fields = ("name", "slug")
    ordering = ("-created_at",)
    readonly_fields = ("id", "created_at", "updated_at")

    @admin.display(description="Teams")
    def team_count_(self, obj: Organization) -> int:
        return obj.teams.count()


@admin.register(Team)
class TeamAdmin(ModelAdmin):
    list_display = ("name", "organization", "study_count_", "created_at")
    list_filter = ("organization",)
    search_fields = ("name", "organization__name")
    autocomplete_fields = ("organization",)
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-created_at",)

    @admin.display(description="Studies")
    def study_count_(self, obj: Team) -> int:
        return obj.studies.count()


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(ModelAdmin):
    list_display = ("user", "organization", "role", "created_at")
    list_filter = ("role", "organization")
    search_fields = ("user__email", "organization__name")
    autocomplete_fields = ("user", "organization")
    readonly_fields = ("id", "created_at", "updated_at")


# ── Studies ──────────────────────────────────────────────


@admin.register(Study)
class StudyAdmin(ModelAdmin):
    list_display = (
        "name_or_goal",
        "team",
        "status",
        "interview_mode",
        "target_completed_count",
        "created_at",
    )
    list_filter = ("status", "interview_mode", "team__organization")
    search_fields = ("name", "research_goal", "slug")
    autocomplete_fields = ("team", "created_by")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-created_at",)
    fieldsets = (
        (
            "Identity",
            {"fields": ("id", "name", "slug", "team", "created_by", "status", "interview_mode")},
        ),
        (
            "Research goal",
            {"fields": ("research_goal", "research_background", "hypothesis", "research_objectives")},
        ),
        (
            "Codebook & analysis",
            {"fields": ("codebook", "success_metrics")},
        ),
        (
            "Recruitment plan",
            {
                "fields": (
                    "target_audience",
                    "target_completed_count",
                    "recruitment_quotas",
                )
            },
        ),
        (
            "Conductor config",
            {"fields": ("estimated_minutes", "section_count_override", "barge_in_enabled")},
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Study", ordering="name")
    def name_or_goal(self, obj: Study) -> str:
        return obj.name or (obj.research_goal[:48] + "…" if len(obj.research_goal) > 48 else obj.research_goal)


@admin.register(StudyLink)
class StudyLinkAdmin(ModelAdmin):
    list_display = ("slug", "study", "is_active", "clicks", "last_clicked_at", "created_at")
    list_filter = ("is_active",)
    search_fields = ("slug", "study__name")
    autocomplete_fields = ("study", "team")
    readonly_fields = ("id", "clicks", "last_clicked_at", "created_at", "updated_at")


@admin.register(StudyTemplate)
class StudyTemplateAdmin(ModelAdmin):
    list_display = ("name", "category", "interview_mode", "is_system", "team")
    list_filter = ("category", "interview_mode", "is_system")
    search_fields = ("name", "description")
    autocomplete_fields = ("team",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(StudyTrigger)
class StudyTriggerAdmin(ModelAdmin):
    list_display = ("study", "condition_type", "event_name", "is_active")
    list_filter = ("condition_type", "is_active")
    search_fields = ("event_name", "study__name")
    autocomplete_fields = ("team", "study")
    readonly_fields = ("id", "created_at", "updated_at")


# ── Stimuli / Screener / Concept ─────────────────────────


@admin.register(Stimulus)
class StimulusAdmin(ModelAdmin):
    list_display = ("study", "kind", "title", "created_at")
    list_filter = ("kind",)
    search_fields = ("title",)
    autocomplete_fields = ("team", "study")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Screener)
class ScreenerAdmin(ModelAdmin):
    list_display = ("study", "team", "created_at")
    search_fields = ("study__name",)
    autocomplete_fields = ("team", "study")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Concept)
class ConceptAdmin(ModelAdmin):
    list_display = ("label", "block", "rank", "created_at")
    search_fields = ("label",)
    autocomplete_fields = ("block", "stimulus")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ConceptBlock)
class ConceptBlockAdmin(ModelAdmin):
    list_display = ("title", "study", "rotation", "created_at")
    list_filter = ("rotation",)
    search_fields = ("title",)
    autocomplete_fields = ("team", "study")
    readonly_fields = ("id", "created_at", "updated_at")


# ── Interview ────────────────────────────────────────────


@admin.register(InterviewGuide)
class InterviewGuideAdmin(ModelAdmin):
    list_display = ("study", "version", "is_current", "language", "created_at")
    list_filter = ("is_current", "language")
    search_fields = ("study__name", "version")
    autocomplete_fields = ("team", "study")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Participant)
class ParticipantAdmin(ModelAdmin):
    list_display = ("display_name", "team", "external_id", "email", "created_at")
    list_filter = ("team",)
    search_fields = ("name", "external_id", "email")
    autocomplete_fields = ("team",)
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-created_at",)

    @admin.display(description="Participant")
    def display_name(self, obj: Participant) -> str:
        return obj.name or obj.external_id or obj.email or "(anonymous)"


@admin.register(Participation)
class ParticipationAdmin(ModelAdmin):
    list_display = ("study", "participant", "status", "source", "is_preview", "trace_id_short", "created_at")
    list_filter = ("status", "source", "is_preview")
    search_fields = ("study__name", "participant__name", "participant__email", "trace_id")
    autocomplete_fields = ("team", "study", "participant")
    readonly_fields = ("id", "created_at", "updated_at", "browser_token", "trace_id", "trail_link")

    @admin.display(description="trace")
    def trace_id_short(self, obj):
        return str(obj.trace_id)[:8] if obj.trace_id else ""

    @admin.display(description="Trail")
    def trail_link(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        if not obj.pk:
            return ""
        url = reverse("admin:merism_participation_trail", args=[obj.pk])
        return format_html('<a href="{}" target="_blank">open trail →</a>', url)

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom = [
            path(
                "<uuid:participation_id>/trail/",
                self.admin_site.admin_view(self.trail_view),
                name="merism_participation_trail",
            ),
        ]
        return custom + urls

    def trail_view(self, request, participation_id):
        """Aggregate timeline for one Participation by ``trace_id``.

        Joins deliveries, session, events, and insight into a single
        chronological view. Useful for "what happened to participant X"
        triage.
        """
        from django.http import Http404
        from django.shortcuts import render
        from merism.models import (
            DeliveryRecord, InterviewSession, Participation, SessionEvent, SessionInsight,
        )
        try:
            p = Participation.objects.select_related("study", "participant").get(pk=participation_id)
        except Participation.DoesNotExist:
            raise Http404()

        timeline = []
        for d in DeliveryRecord.objects.filter(trace_id=p.trace_id).order_by("created_at"):
            timeline.append({"ts": d.created_at, "kind": "delivery", "what": f"{d.status} → {d.recipient_id}", "ref": str(d.id)})
        timeline.append({"ts": p.created_at, "kind": "participation", "what": f"created ({p.status})", "ref": str(p.id)})
        if p.consented_at:
            timeline.append({"ts": p.consented_at, "kind": "participation", "what": "consented", "ref": ""})
        for s in InterviewSession.objects.filter(trace_id=p.trace_id).order_by("created_at"):
            timeline.append({"ts": s.created_at, "kind": "session", "what": f"{s.mode}/{s.status}", "ref": str(s.id)})
            for ev in SessionEvent.objects.filter(session=s).order_by("seq"):
                timeline.append({"ts": ev.created_at, "kind": f"event:{ev.kind}", "what": str(ev.payload)[:200], "ref": f"seq={ev.seq}"})
        for ins in SessionInsight.objects.filter(trace_id=p.trace_id).order_by("created_at"):
            timeline.append({"ts": ins.created_at, "kind": "insight", "what": (ins.summary or "")[:200], "ref": str(ins.id)})
        timeline.sort(key=lambda r: r["ts"] or p.created_at)
        return render(
            request,
            "admin/merism/participation_trail.html",
            {"participation": p, "timeline": timeline, "opts": Participation._meta, **self.admin_site.each_context(request)},
        )


@admin.register(InterviewSession)
class InterviewSessionAdmin(ModelAdmin):
    list_display = ("study", "mode", "status", "started_at", "ended_at", "created_at")
    list_filter = ("mode", "status")
    search_fields = ("study__name",)
    autocomplete_fields = ("team", "study", "participation", "guide")
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "transcript",
        "moderator_state",
        "decision_log",
    )
    ordering = ("-created_at",)
    fieldsets = (
        ("Identity", {"fields": ("id", "team", "study", "participation", "guide")}),
        ("Lifecycle", {"fields": ("mode", "status", "started_at", "ended_at")}),
        ("Media", {"fields": ("audio_s3_key", "video_s3_key", "vision_frames")}),
        ("Transcript (read-only)", {"fields": ("transcript",)}),
        ("Conductor state (read-only)", {"fields": ("moderator_state", "decision_log")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(InterviewRecording)
class InterviewRecordingAdmin(ModelAdmin):
    list_display = ("session", "duration_s", "size_bytes", "is_deleted")
    list_filter = ("is_deleted",)
    autocomplete_fields = ("team", "session")
    readonly_fields = ("id", "created_at", "updated_at")


# ── Recruitment ──────────────────────────────────────────


class ChannelTargetInline(admin.TabularInline):
    model = ChannelTarget
    extra = 0
    fields = ("name", "recipient_id", "recipient_kind", "is_default", "is_active", "metadata")


@admin.register(ChannelConfig)
class ChannelConfigAdmin(ModelAdmin):
    list_display = (
        "name",
        "channel_type",
        "team",
        "status",
        "consecutive_failures",
        "last_healthy_at",
    )
    list_filter = ("channel_type", "status")
    search_fields = ("name", "team__name")
    autocomplete_fields = ("team",)
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        # Never display the ciphertext; Fernet blob is for machine use.
        "credentials_encrypted",
        "last_healthy_at",
        "last_error",
        "consecutive_failures",
    )
    inlines = [ChannelTargetInline]


@admin.register(ChannelHealthCheck)
class ChannelHealthCheckAdmin(ModelAdmin):
    list_display = ("channel", "ok", "latency_ms", "created_at")
    list_filter = ("ok",)
    autocomplete_fields = ("team", "channel")
    readonly_fields = ("id", "created_at", "updated_at", "ok", "latency_ms", "error")

    def has_add_permission(self, request: Any) -> bool:
        return False  # Log table, written by beat task.


@admin.register(ChannelTarget)
class ChannelTargetAdmin(ModelAdmin):
    list_display = ("name", "channel", "recipient_kind", "is_default", "is_active", "team")
    list_filter = ("recipient_kind", "is_default", "is_active", "channel__channel_type")
    search_fields = ("name", "recipient_id", "channel__name", "team__name")
    autocomplete_fields = ("team", "channel")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(MessageTemplate)
class MessageTemplateAdmin(ModelAdmin):
    list_display = ("name", "channel_type", "is_system", "team")
    list_filter = ("channel_type", "is_system")
    search_fields = ("name",)
    autocomplete_fields = ("team",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(RecruitmentBroadcast)
class RecruitmentBroadcastAdmin(ModelAdmin):
    list_display = ("study", "channel", "status", "retry_count", "created_at")
    list_filter = ("status",)
    search_fields = ("study__name", "channel__name")
    autocomplete_fields = ("team", "study", "study_link", "channel", "template")
    readonly_fields = ("id", "created_at", "updated_at", "counters", "approved_snapshot")


@admin.register(DeliveryRecord)
class DeliveryRecordAdmin(ModelAdmin):
    list_display = ("broadcast", "recipient_id", "status", "sent_at", "delivered_at")
    list_filter = ("status",)
    search_fields = ("recipient_id", "message_id")
    autocomplete_fields = ("team", "broadcast")
    readonly_fields = ("id", "created_at", "updated_at")


# ── Analysis / Reports ───────────────────────────────────


@admin.register(SessionQuote)
class SessionQuoteAdmin(ModelAdmin):
    list_display = ("snippet", "study", "session", "importance", "created_at")
    list_filter = ("study",)
    search_fields = ("text",)
    autocomplete_fields = ("team", "study", "session")
    readonly_fields = ("id", "created_at", "updated_at", "embedded_at")
    ordering = ("-importance",)

    @admin.display(description="Quote")
    def snippet(self, obj: SessionQuote) -> str:
        text = obj.text.replace("\n", " ")
        return text[:80] + "…" if len(text) > 80 else text


@admin.register(SessionInsight)
class SessionInsightAdmin(ModelAdmin):
    list_display = ("session", "summary_preview", "created_at")
    autocomplete_fields = ("team", "session")
    readonly_fields = ("id", "created_at", "updated_at", "highlights", "tags", "extracted_tasks")

    @admin.display(description="Summary")
    def summary_preview(self, obj: SessionInsight) -> str:
        text = (obj.summary or "").replace("\n", " ")
        return text[:80] + "…" if len(text) > 80 else text


@admin.register(StudyReport)
class StudyReportAdmin(ModelAdmin):
    list_display = ("study", "status", "generated_by", "generated_at", "created_at")
    list_filter = ("status",)
    autocomplete_fields = ("team", "study")
    readonly_fields = ("id", "created_at", "updated_at", "content", "charts")


@admin.register(AggregateSynthesis)
class AggregateSynthesisAdmin(ModelAdmin):
    list_display = ("study", "headline_preview", "generated_at")
    autocomplete_fields = ("team", "study")
    readonly_fields = ("id", "created_at", "updated_at", "themes", "covered_goals")

    @admin.display(description="Headline")
    def headline_preview(self, obj: AggregateSynthesis) -> str:
        return (obj.headline or "")[:80]


@admin.register(CustomReportQuery)
class CustomReportQueryAdmin(ModelAdmin):
    list_display = ("question_preview", "study", "pinned", "created_at")
    list_filter = ("pinned",)
    search_fields = ("question",)
    autocomplete_fields = ("team", "study", "created_by")
    readonly_fields = ("id", "created_at", "updated_at", "citations")

    @admin.display(description="Question")
    def question_preview(self, obj: CustomReportQuery) -> str:
        return obj.question[:80]


# ── Knowledge ────────────────────────────────────────────


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(ModelAdmin):
    list_display = ("title", "source_type", "team", "created_at")
    list_filter = ("source_type",)
    search_fields = ("title", "source_id")
    autocomplete_fields = ("team",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(KnowledgeChunk)
class KnowledgeChunkAdmin(ModelAdmin):
    list_display = ("chunk_preview", "document", "chunk_index", "team", "created_at")
    search_fields = ("content",)
    autocomplete_fields = ("team", "document")
    readonly_fields = ("id", "created_at", "updated_at")

    @admin.display(description="Chunk")
    def chunk_preview(self, obj: KnowledgeChunk) -> str:
        text = (obj.content or "").replace("\n", " ")
        return text[:60] + "…" if len(text) > 60 else text


# ── Dashboard callback (UNFOLD DASHBOARD_CALLBACK) ───────


def dashboard_callback(request: Any, context: dict[str, Any]) -> dict[str, Any]:
    """Inject Merism KPIs + sparkline + channel health into /admin/ home.

    Called by django-unfold for the admin index page. The template at
    ``merism/templates/admin/index.html`` reads the added keys.
    """

    now = timezone.now()
    week_ago = now - timedelta(days=7)
    since = now - timedelta(days=14)
    one_hour_ago = now - timedelta(hours=1)

    kpi = {
        "org_count": Organization.objects.count(),
        "team_count": Team.objects.count(),
        "study_count": Study.objects.count(),
        "active_study_count": Study.objects.filter(
            status__in=[
                Study.Status.RECRUITING,
                Study.Status.ACTIVE,
                Study.Status.READY,
            ]
        ).count(),
        "session_count": InterviewSession.objects.count(),
        "completed_week": InterviewSession.objects.filter(
            status=InterviewSession.Status.COMPLETED,
            ended_at__gte=week_ago,
        ).count(),
        "participant_count": Participant.objects.count(),
        "quote_count": SessionQuote.objects.count(),
        "insight_count": SessionInsight.objects.count(),
    }

    daily_rows = (
        InterviewSession.objects.filter(created_at__gte=since)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    sessions_per_day = [
        {"day": r["day"].isoformat(), "count": r["count"]} for r in daily_rows
    ]
    max_count = max((p["count"] for p in sessions_per_day), default=0) or 1
    spark_bars = [
        {
            "day": p["day"],
            "day_short": p["day"][5:],
            "count": p["count"],
            "height_pct": int(round(p["count"] / max_count * 100)),
        }
        for p in sessions_per_day
    ]

    health_rows = (
        ChannelHealthCheck.objects.filter(created_at__gte=one_hour_ago)
        .values("ok")
        .annotate(count=Count("id"))
    )
    channel_health = {("ok" if r["ok"] else "failing"): r["count"] for r in health_rows}

    recent_sessions = (
        InterviewSession.objects.select_related("study", "team")
        .order_by("-created_at")[:10]
    )

    context.update(
        {
            "merism_kpi": kpi,
            "merism_spark_bars": spark_bars,
            "merism_channel_health": channel_health,
            "merism_recent_sessions": recent_sessions,
        }
    )
    return context


@admin.register(SessionEvent)
class SessionEventAdmin(admin.ModelAdmin):
    list_display = ("session", "seq", "kind", "created_at")
    list_filter = ("kind",)
    search_fields = ("session__id", "trace_id")
    readonly_fields = ("session", "seq", "kind", "trace_id", "payload", "created_at")
    ordering = ("-created_at",)


# ── Link tracking ────────────────────────────────────────


@admin.register(LinkClick)
class LinkClickAdmin(ModelAdmin):
    list_display = ("study_link", "trigger", "device_type", "browser", "referer", "utm_source", "trace_id_short", "created_at")
    list_filter = ("trigger", "device_type", "browser", "os")
    search_fields = ("identity_hash", "referer", "utm_source", "utm_campaign", "trace_id")
    autocomplete_fields = ("team", "study_link", "participation", "referrer_participation")
    readonly_fields = ("id", "identity_hash", "ip_hash", "trace_id", "created_at", "updated_at")
    ordering = ("-created_at",)

    @admin.display(description="trace")
    def trace_id_short(self, obj: LinkClick) -> str:
        return str(obj.trace_id)[:8]

    def has_add_permission(self, request: Any) -> bool:
        return False  # Log table, written by resolve_link view.


@admin.register(LinkShareEvent)
class LinkShareEventAdmin(ModelAdmin):
    list_display = ("study_link", "action", "sharer_participation", "trace_id_short", "created_at")
    list_filter = ("action",)
    search_fields = ("trace_id",)
    autocomplete_fields = ("team", "study_link", "sharer_participation")
    readonly_fields = ("id", "trace_id", "created_at", "updated_at")
    ordering = ("-created_at",)

    @admin.display(description="trace")
    def trace_id_short(self, obj: LinkShareEvent) -> str:
        return str(obj.trace_id)[:8]

    def has_add_permission(self, request: Any) -> bool:
        return False


# ── Invitations / Inbox ──────────────────────────────────


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("study_link", "recipient_display", "status", "delivered_at", "accepted_at", "created_at")
    list_filter = ("status",)
    search_fields = ("recipient_display", "recipient_hash", "token", "trace_id")
    autocomplete_fields = ("team", "study_link", "participation")
    readonly_fields = ("id", "token", "trace_id", "recipient_hash", "created_at", "updated_at")


@admin.register(InboxItem)
class InboxItemAdmin(admin.ModelAdmin):
    list_display = ("team", "kind", "title", "created_at")
    list_filter = ("kind",)
    search_fields = ("title", "body", "ref_id", "trace_id")
    readonly_fields = ("id", "team", "kind", "ref_kind", "ref_id", "title", "body", "payload", "read_by", "trace_id", "created_at", "updated_at")


# ── LLM Gateway (DEPRECATED — use ServiceSettings via admin_service_settings.py) ──
# Old LLMProvider/LLMRoute/LLMBudget admin registrations removed.
# Models kept temporarily for legacy fallback in llm_gateway/client.py.


# ── Service Settings (Dograh-style provider config) ──────
import merism.admin_service_settings  # noqa: F401, E402
