"""Link tracking API views.

Provides researchers with:
- Click statistics per link (breakdown by device, source, referer)
- Funnel analysis (delivery → click → consent → session → completed)
- Click event list with upstream/downstream chain
"""

from __future__ import annotations

from dataclasses import asdict

from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from merism.api.base import TeamScopedModelViewSet
from merism.models import LinkClick, LinkShareEvent, StudyLink
from merism.participant.funnel import (
    click_stats_for_link,
    compute_link_funnel,
    compute_study_funnel,
)


class LinkClickSerializer(serializers.ModelSerializer):
    referrer_participation_id = serializers.UUIDField(
        source="referrer_participation.id", read_only=True, default=None
    )

    class Meta:
        model = LinkClick
        fields = [
            "id",
            "study_link_id",
            "identity_hash",
            "participation_id",
            "trace_id",
            "referer",
            "referer_url",
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "device_type",
            "browser",
            "os",
            "country",
            "trigger",
            "is_unique",
            "referrer_participation_id",
            "created_at",
        ]
        read_only_fields = fields


class LinkShareEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = LinkShareEvent
        fields = [
            "id",
            "study_link_id",
            "action",
            "sharer_participation_id",
            "trace_id",
            "created_at",
        ]
        read_only_fields = fields


class LinkClickViewSet(TeamScopedModelViewSet):
    """Read-only viewset for link click events."""

    queryset = LinkClick.objects.select_related("referrer_participation").order_by("-created_at")
    serializer_class = LinkClickSerializer
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        # Filter by study_link if provided
        link_id = self.request.query_params.get("study_link")
        if link_id:
            qs = qs.filter(study_link_id=link_id)
        study_id = self.request.query_params.get("study")
        if study_id:
            qs = qs.filter(study_link__study_id=study_id)
        return qs

    @action(detail=False, methods=["get"], url_path="stats/(?P<link_id>[^/.]+)")
    def stats(self, request, link_id=None):
        """GET /api/link-clicks/stats/<link_id>/ — aggregate click stats."""
        try:
            link = StudyLink.objects.get(id=link_id, team=self.get_team())
        except StudyLink.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(click_stats_for_link(link))

    @action(detail=False, methods=["get"], url_path="funnel/(?P<study_id>[^/.]+)")
    def funnel(self, request, study_id=None):
        """GET /api/link-clicks/funnel/<study_id>/ — study-level funnel."""
        from merism.models import Study

        try:
            study = Study.objects.get(id=study_id, team=self.get_team())
        except Study.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        study_funnel = compute_study_funnel(study)
        per_link = compute_link_funnel(study)

        return Response({
            "study_id": str(study.id),
            "funnel": [asdict(s) for s in study_funnel],
            "per_link": [
                {
                    "study_link_id": lf.study_link_id,
                    "slug": lf.slug,
                    "total_clicks": lf.total_clicks,
                    "unique_clicks": lf.unique_clicks,
                    "stages": [asdict(s) for s in lf.stages],
                }
                for lf in per_link
            ],
        })

    @action(detail=False, methods=["get"], url_path="chain/(?P<participation_id>[^/.]+)")
    def chain(self, request, participation_id=None):
        """GET /api/link-clicks/chain/<participation_id>/ — upstream/downstream chain."""
        team = self.get_team()

        # Upstream: who referred this participation?
        upstream_clicks = LinkClick.objects.filter(
            participation_id=participation_id, team=team
        ).select_related("referrer_participation")

        upstream = None
        for click in upstream_clicks:
            if click.referrer_participation_id:
                upstream = str(click.referrer_participation_id)
                break

        # Downstream: who did this participation refer?
        downstream_clicks = LinkClick.objects.filter(
            referrer_participation_id=participation_id, team=team
        ).values_list("participation_id", flat=True).distinct()

        return Response({
            "participation_id": participation_id,
            "upstream_participation_id": upstream,
            "downstream_participation_ids": [
                str(pid) for pid in downstream_clicks if pid
            ],
        })


class LinkShareEventViewSet(TeamScopedModelViewSet):
    """Read-only viewset for link share events."""

    queryset = LinkShareEvent.objects.order_by("-created_at")
    serializer_class = LinkShareEventSerializer
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        link_id = self.request.query_params.get("study_link")
        if link_id:
            qs = qs.filter(study_link_id=link_id)
        return qs
