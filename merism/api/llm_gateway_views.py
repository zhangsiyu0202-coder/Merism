"""LLM Gateway Admin API — DRF viewsets for LLMProvider, LLMRoute, LLMBudget."""

from __future__ import annotations

from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from merism.api.base import TeamScopedModelViewSet
from merism.llm_gateway.presets import load_presets, presets_for_protocol
from merism.models.llm_gateway import LLMBudget, LLMProvider, LLMRoute
from merism.recruitment.crypto import decrypt_credentials, encrypt_credentials


# ── Serializers ────────────────────────────────────────────


class LLMProviderSerializer(serializers.ModelSerializer):
    """Provider serializer. Credentials are write-only (never returned)."""

    credentials = serializers.DictField(write_only=True, required=False)
    has_credentials = serializers.SerializerMethodField()

    class Meta:
        model = LLMProvider
        fields = [
            "id", "display_name", "protocol", "base_url", "model",
            "credentials", "has_credentials", "extra_headers", "is_active",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_has_credentials(self, obj: LLMProvider) -> bool:
        return bool(obj.credentials_encrypted)

    def create(self, validated_data):
        creds = validated_data.pop("credentials", None)
        if creds:
            validated_data["credentials_encrypted"] = encrypt_credentials(creds)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        creds = validated_data.pop("credentials", None)
        if creds:
            validated_data["credentials_encrypted"] = encrypt_credentials(creds)
        return super().update(instance, validated_data)


class LLMRouteSerializer(serializers.ModelSerializer):
    primary_display = serializers.CharField(source="primary.display_name", read_only=True)
    fallback_display = serializers.CharField(source="fallback.display_name", read_only=True, default=None)

    class Meta:
        model = LLMRoute
        fields = [
            "id", "logical_name", "primary", "primary_display",
            "fallback", "fallback_display", "temperature",
            "max_output_tokens", "timeout_seconds", "max_retries",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class LLMBudgetSerializer(serializers.ModelSerializer):
    is_over_soft_limit = serializers.BooleanField(read_only=True)
    is_over_hard_limit = serializers.BooleanField(read_only=True)

    class Meta:
        model = LLMBudget
        fields = [
            "id", "period", "monthly_cap_usd", "soft_limit_pct",
            "hard_limit_action", "current_spent_usd",
            "is_over_soft_limit", "is_over_hard_limit",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "current_spent_usd", "created_at", "updated_at"]


# ── ViewSets ──────────────────────────────────────────────


class LLMProviderViewSet(TeamScopedModelViewSet):
    queryset = LLMProvider.objects.all()
    serializer_class = LLMProviderSerializer

    def get_queryset(self):
        team = self.get_team()
        # Show team-specific + global (team=None) providers
        return LLMProvider.objects.filter(team__in=[team, None]).order_by("-created_at")

    @action(detail=False, methods=["get"])
    def presets(self, request):
        """List available provider presets for quick setup."""
        protocol = request.query_params.get("protocol")
        if protocol:
            data = presets_for_protocol(protocol)
        else:
            data = load_presets()
        return Response(data)


class LLMRouteViewSet(TeamScopedModelViewSet):
    queryset = LLMRoute.objects.select_related("primary", "fallback").all()
    serializer_class = LLMRouteSerializer


class LLMBudgetViewSet(TeamScopedModelViewSet):
    queryset = LLMBudget.objects.all()
    serializer_class = LLMBudgetSerializer
    http_method_names = ["get", "head", "options", "post", "patch"]  # no DELETE
