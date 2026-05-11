"""Home scene stats endpoint.

Returns a single compact object the Home page paints with —
``sessions_week``, ``studies_total``, ``studies_active``,
``talk_time_hours``, ``participants_total``, ``insights_total``.

All counts are strictly team-scoped via
:func:`merism.api.base._team_from_request`.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import DurationField, ExpressionWrapper, F, Sum
from django.http import Http404
from django.utils import timezone
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from merism.api.base import _team_from_request
from merism.models import (
    InterviewSession,
    Participant,
    SessionInsight,
    Study,
)


ACTIVE_STATUSES = {
    Study.Status.READY,
    Study.Status.RECRUITING,
    Study.Status.ACTIVE,
}


class HomeStatsView(APIView):
    """``GET /api/home/stats/`` — aggregate counters for the Home page."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request) -> Response:
        team = _team_from_request(request)
        if team is None:
            raise Http404("No team membership for this user.")

        week_ago = timezone.now() - timedelta(days=7)

        studies_qs = Study.objects.filter(team=team)
        sessions_qs = InterviewSession.objects.filter(study__team=team)
        participants_qs = Participant.objects.filter(team=team)
        insights_qs = SessionInsight.objects.filter(session__study__team=team)

        studies_total = studies_qs.count()
        studies_active = studies_qs.filter(status__in=ACTIVE_STATUSES).count()

        sessions_week = sessions_qs.filter(created_at__gte=week_ago).count()

        # Talk time: sum of (ended_at - started_at) across completed sessions.
        # Uses a DurationField ExpressionWrapper so Postgres does the math.
        duration_expr = ExpressionWrapper(
            F("ended_at") - F("started_at"),
            output_field=DurationField(),
        )
        total_duration: timedelta | None = (
            sessions_qs.filter(
                status=InterviewSession.Status.COMPLETED,
                started_at__isnull=False,
                ended_at__isnull=False,
            )
            .annotate(dur=duration_expr)
            .aggregate(total=Sum("dur"))
            .get("total")
        )
        talk_time_hours = (
            round(total_duration.total_seconds() / 3600, 1)
            if total_duration is not None
            else 0.0
        )

        participants_total = participants_qs.count()
        insights_total = insights_qs.count()

        payload: dict[str, Any] = {
            "sessions_week": sessions_week,
            "studies_total": studies_total,
            "studies_active": studies_active,
            "talk_time_hours": talk_time_hours,
            "participants_total": participants_total,
            "insights_total": insights_total,
        }
        return Response(payload)
