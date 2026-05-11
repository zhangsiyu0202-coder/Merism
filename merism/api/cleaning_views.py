"""Cleaning Admin API — DRF viewset for Glossary."""

from __future__ import annotations

from rest_framework import serializers

from merism.api.base import TeamScopedModelViewSet
from merism.models import Glossary


class GlossarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Glossary
        fields = [
            "id", "study", "canonical", "variants",
            "case_insensitive", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class GlossaryViewSet(TeamScopedModelViewSet):
    queryset = Glossary.objects.all()
    serializer_class = GlossarySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        study_id = self.request.query_params.get("study")
        if study_id == "team":
            qs = qs.filter(study__isnull=True)
        elif study_id:
            qs = qs.filter(study_id=study_id)
        return qs.order_by("canonical")
