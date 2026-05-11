"""Analysis API — DRF viewsets for Theme, CoverageSnapshot, StudyGoal."""

from __future__ import annotations

from rest_framework import serializers, viewsets

from merism.api.base import TeamScopedModelViewSet
from merism.models import CohortSegment, CoverageSnapshot, StudyGoal, Theme


class StudyGoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyGoal
        fields = [
            "id", "study", "text", "priority", "display_order",
            "coverage", "is_answered", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "coverage", "is_answered", "created_at", "updated_at"]


class ThemeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Theme
        fields = [
            "id", "study", "name", "description",
            "representative_quote_ids", "session_ids",
            "session_count", "quote_count", "sentiment_mix",
            "status", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "representative_quote_ids", "session_ids",
            "session_count", "quote_count", "sentiment_mix",
            "created_at", "updated_at",
        ]


class CoverageSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoverageSnapshot
        fields = [
            "id", "study", "goal_coverage", "overall_coverage",
            "gaps", "session_count", "recommendations", "created_at",
        ]
        read_only_fields = fields  # all read-only


class CohortSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CohortSegment
        fields = [
            "id", "study", "name", "description",
            "selector", "participation_ids", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "participation_ids", "created_at", "updated_at"]


# ── Viewsets ───────────────────────────────────────────────


class StudyGoalViewSet(TeamScopedModelViewSet):
    queryset = StudyGoal.objects.all()
    serializer_class = StudyGoalSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        study_id = self.request.query_params.get("study")
        if study_id:
            qs = qs.filter(study_id=study_id)
        return qs.order_by("study", "display_order")


class ThemeViewSet(TeamScopedModelViewSet):
    queryset = Theme.objects.all()
    serializer_class = ThemeSerializer
    http_method_names = ["get", "patch", "head", "options"]  # read + status updates only

    def get_queryset(self):
        qs = super().get_queryset()
        study_id = self.request.query_params.get("study")
        if study_id:
            qs = qs.filter(study_id=study_id)
        return qs.exclude(status=Theme.Status.ARCHIVED).order_by("-session_count")


class CoverageSnapshotViewSet(TeamScopedModelViewSet):
    queryset = CoverageSnapshot.objects.all()
    serializer_class = CoverageSnapshotSerializer
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        study_id = self.request.query_params.get("study")
        if study_id:
            qs = qs.filter(study_id=study_id)
        return qs.order_by("-created_at")


class CohortSegmentViewSet(TeamScopedModelViewSet):
    queryset = CohortSegment.objects.all()
    serializer_class = CohortSegmentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        study_id = self.request.query_params.get("study")
        if study_id:
            qs = qs.filter(study_id=study_id)
        return qs
