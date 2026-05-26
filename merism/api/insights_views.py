"""Insights & Custom Reports API — DRF viewsets.

Endpoints:
- /api/study-insights/         — StudyInsights CRUD + re-run action
- /api/insight-highlights/     — read-only highlights
- /api/insight-findings/       — read-only findings
- /api/custom-reports/         — CustomReport CRUD + generate action
- /api/report-segments/        — ReportSegment CRUD
- /api/report-questions/       — ReportQuestion CRUD
- /api/custom-reports/:id/export/  — CSV/PDF export
- /api/shared/report/:token/   — public share (unauthenticated)
"""

from __future__ import annotations

import csv
import io

from django.http import HttpResponse
from rest_framework import serializers, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from merism.api.base import TeamScopedModelViewSet
from merism.models import (
    CustomReport,
    InsightFinding,
    InsightHighlight,
    ReportQuestion,
    ReportSegment,
    StudyInsights,
)

# ── Serializers ────────────────────────────────────────────


class StudyInsightsSerializer(serializers.ModelSerializer):
    highlights_count = serializers.IntegerField(source="highlights.count", read_only=True)
    findings_count = serializers.IntegerField(source="findings.count", read_only=True)
    # Derive ``status`` from observable reality rather than trusting the
    # stored field. The DB column can drift out of sync if a worker is
    # killed mid-task, if a rerun() races with the task's final save,
    # or if the queue is wiped by a redis flush. A serializer that
    # asks "what does the world actually look like?" is self-healing:
    # the UI tells the truth even when the column lies.
    #
    # Three resolution rules:
    #
    # 1. If the underlying data is fully populated → ``ready``. The
    #    task succeeded; the column is just stale.
    # 2. If the column says ``generating`` but generation can never
    #    succeed (no completed interviews to analyze) → ``failed``.
    #    Otherwise the frontend polls forever waiting for a task
    #    that has nothing to feed on.
    # 3. Otherwise → trust the column. Genuine in-flight generation
    #    is the common case for a healthy fresh task.
    status = serializers.SerializerMethodField()

    def get_status(self, obj: StudyInsights) -> str:
        # Rule 1: data is intact → trust the data.
        data_complete = (
            obj.generated_at is not None
            and bool(obj.executive_summary)
            and obj.highlights.exists()
            and obj.findings.exists()
        )
        if data_complete:
            return StudyInsights.Status.READY

        # Rule 2: stuck at generating but generation cannot possibly
        # succeed. ``actual_completed_count`` is a property that runs
        # ``Participation.objects.filter(status=COMPLETED).count()`` —
        # if it's zero, the task's first guard returns FAILED with
        # "No completed interviews to analyze" anyway. We mirror that
        # outcome at the read path so a stranded row surfaces as
        # ``failed`` instead of looping the frontend's poller forever.
        if (
            obj.status == StudyInsights.Status.GENERATING
            and obj.study.actual_completed_count == 0
        ):
            return StudyInsights.Status.FAILED

        # Rule 3: trust the column.
        return obj.status

    def get_error_message(self, obj: StudyInsights) -> str:
        # Mirror ``get_status``'s synthesized FAILED state with a
        # human-readable reason so the UI doesn't show an empty
        # error string next to a "Failed" badge.
        if (
            obj.status == StudyInsights.Status.GENERATING
            and obj.study.actual_completed_count == 0
            and not obj.executive_summary
        ):
            return "无已完成的访谈可供分析。"
        return obj.error_message or ""

    error_message = serializers.SerializerMethodField()

    class Meta:
        model = StudyInsights
        fields = [
            "id",
            "study",
            "status",
            "completed_interviews",
            "avg_session_minutes",
            "interview_topics",
            "executive_summary",
            "generated_at",
            "error_message",
            "highlights_count",
            "findings_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "completed_interviews",
            "avg_session_minutes",
            "interview_topics",
            "executive_summary",
            "generated_at",
            "error_message",
            "highlights_count",
            "findings_count",
            "created_at",
            "updated_at",
        ]


class InsightHighlightSerializer(serializers.ModelSerializer):
    class Meta:
        model = InsightHighlight
        fields = [
            "id",
            "insights",
            "headline",
            "summary",
            "icon",
            "display_order",
            "linked_finding",
            "created_at",
        ]
        read_only_fields = fields


class InsightFindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = InsightFinding
        fields = [
            "id",
            "insights",
            "title",
            "summary",
            "display_order",
            "chart_spec",
            "chart_interpretation",
            "themes",
            "subthemes",
            "insight_nuggets",
            "supporting_evidence",
            "created_at",
        ]
        read_only_fields = fields


class CustomReportSerializer(serializers.ModelSerializer):
    questions_count = serializers.IntegerField(source="questions.count", read_only=True)
    segments_count = serializers.IntegerField(source="segments.count", read_only=True)
    share_url = serializers.CharField(read_only=True)

    class Meta:
        model = CustomReport
        fields = [
            "id",
            "study",
            "title",
            "status",
            "ai_synthesis",
            "share_token",
            "is_public",
            "share_url",
            "questions_count",
            "segments_count",
            "generated_at",
            "error_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "ai_synthesis",
            "share_token",
            "share_url",
            "questions_count",
            "segments_count",
            "generated_at",
            "error_message",
            "created_at",
            "updated_at",
        ]


class ReportSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportSegment
        fields = [
            "id",
            "report",
            "name",
            "selector",
            "participation_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "participation_ids", "created_at", "updated_at"]


class ReportQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportQuestion
        fields = [
            "id",
            "report",
            "question_number",
            "title",
            "question_type",
            "status",
            "ai_summary",
            "chart_spec",
            "themes",
            "quotes",
            "segment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "ai_summary",
            "chart_spec",
            "themes",
            "quotes",
            "created_at",
            "updated_at",
        ]


# ── Viewsets ───────────────────────────────────────────────


class StudyInsightsViewSet(TeamScopedModelViewSet):
    queryset = StudyInsights.objects.all()
    serializer_class = StudyInsightsSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        study_id = self.request.query_params.get("study")
        if study_id:
            qs = qs.filter(study_id=study_id)
        return qs

    def perform_create(self, serializer) -> None:
        """Auto-trigger generation when a StudyInsights record is created."""
        instance = serializer.save(
            team=self.get_team(),
            status=StudyInsights.Status.GENERATING,
        )
        from merism.api.insights_tasks import generate_insights_task

        generate_insights_task.delay(str(instance.id))

    @action(detail=True, methods=["post"])
    def rerun(self, request: Request, pk: str | None = None) -> Response:
        """Trigger re-generation of insights for this study."""
        instance = self.get_object()
        instance.status = StudyInsights.Status.GENERATING
        instance.error_message = ""
        instance.save(update_fields=["status", "error_message", "updated_at"])

        from merism.api.insights_tasks import generate_insights_task

        generate_insights_task.delay(str(instance.id))

        return Response(
            StudyInsightsSerializer(instance).data,
            status=status.HTTP_202_ACCEPTED,
        )


class InsightHighlightViewSet(TeamScopedModelViewSet):
    queryset = InsightHighlight.objects.all()
    serializer_class = InsightHighlightSerializer
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        insights_id = self.request.query_params.get("insights")
        if insights_id:
            qs = qs.filter(insights_id=insights_id)
        return qs.order_by("display_order")


class InsightFindingViewSet(TeamScopedModelViewSet):
    queryset = InsightFinding.objects.all()
    serializer_class = InsightFindingSerializer
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        insights_id = self.request.query_params.get("insights")
        if insights_id:
            qs = qs.filter(insights_id=insights_id)
        return qs.order_by("display_order")


class CustomReportViewSet(TeamScopedModelViewSet):
    queryset = CustomReport.objects.all()
    serializer_class = CustomReportSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        study_id = self.request.query_params.get("study")
        if study_id:
            qs = qs.filter(study_id=study_id)
        return qs.order_by("-created_at")

    @action(detail=True, methods=["post"])
    def generate(self, request: Request, pk: str | None = None) -> Response:
        """Trigger AI generation for all questions in this report."""
        instance = self.get_object()
        instance.status = CustomReport.Status.GENERATING
        instance.error_message = ""
        instance.save(update_fields=["status", "error_message", "updated_at"])

        from merism.api.insights_tasks import generate_report_task

        generate_report_task.delay(str(instance.id))

        return Response(
            CustomReportSerializer(instance).data,
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["post"])
    def toggle_public(self, request: Request, pk: str | None = None) -> Response:
        """Toggle public share link."""
        instance = self.get_object()
        instance.is_public = not instance.is_public
        instance.save(update_fields=["is_public", "updated_at"])
        return Response(CustomReportSerializer(instance).data)

    @action(detail=True, methods=["get"])
    def export_csv(self, request: Request, pk: str | None = None) -> HttpResponse:
        """Export report as CSV."""
        instance = self.get_object()
        questions = instance.questions.order_by("question_number")

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Question #", "Title", "Type", "AI Summary", "Themes"])
        for q in questions:
            themes_str = "; ".join(t.get("name", "") for t in (q.themes or []))
            writer.writerow(
                [
                    f"Q{q.question_number}",
                    q.title,
                    q.get_question_type_display(),
                    q.ai_summary,
                    themes_str,
                ]
            )

        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{instance.title[:50]}.csv"'
        return response

    @action(detail=True, methods=["get"])
    def export_pdf(self, request: Request, pk: str | None = None) -> HttpResponse:
        """Export report as PDF (simple text-based)."""
        instance = self.get_object()
        questions = instance.questions.order_by("question_number")

        # Simple text-based PDF using reportlab if available, else plain text
        lines = [f"Report: {instance.title}\n", f"Study: {instance.study.name}\n"]
        lines.append(f"Generated: {instance.generated_at or 'N/A'}\n\n")

        if instance.ai_synthesis:
            lines.append(f"AI Synthesis:\n{instance.ai_synthesis}\n\n")

        for q in questions:
            lines.append(f"Q{q.question_number}: {q.title}\n")
            lines.append(f"Type: {q.get_question_type_display()}\n")
            if q.ai_summary:
                lines.append(f"Summary: {q.ai_summary}\n")
            lines.append("\n")

        content = "".join(lines)
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{instance.title[:50]}.pdf"'
        return response


class ReportSegmentViewSet(TeamScopedModelViewSet):
    queryset = ReportSegment.objects.all()
    serializer_class = ReportSegmentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        report_id = self.request.query_params.get("report")
        if report_id:
            qs = qs.filter(report_id=report_id)
        return qs


class ReportQuestionViewSet(TeamScopedModelViewSet):
    queryset = ReportQuestion.objects.all()
    serializer_class = ReportQuestionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        report_id = self.request.query_params.get("report")
        if report_id:
            qs = qs.filter(report_id=report_id)
        return qs.order_by("question_number")


# ── Public share endpoint (unauthenticated) ────────────────


@api_view(["GET"])
@permission_classes([AllowAny])
def shared_report_view(request: Request, token: str) -> Response:
    """Public read-only view of a shared report."""
    try:
        report = CustomReport.objects.get(share_token=token, is_public=True)
    except CustomReport.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    questions = report.questions.order_by("question_number")
    segments = report.segments.all()

    return Response(
        {
            "id": str(report.id),
            "title": report.title,
            "study_name": report.study.name,
            "ai_synthesis": report.ai_synthesis,
            "generated_at": report.generated_at,
            "questions": ReportQuestionSerializer(questions, many=True).data,
            "segments": ReportSegmentSerializer(segments, many=True).data,
        }
    )
