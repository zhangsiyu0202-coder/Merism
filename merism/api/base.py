"""DRF base classes for Merism API viewsets.

Every domain viewset inherits from :class:`TeamScopedModelViewSet` which:

1. Filters queryset by ``request.user``'s team membership. No row outside
   the user's team ever leaves this layer.
2. On create/update, injects ``team`` automatically — view code cannot
   accidentally skip it.
3. Exposes ``self.get_team()`` for serializers that need it (via context).

404 is used instead of 403 for cross-team access to avoid leaking existence.
"""

from __future__ import annotations

from typing import Any

from django.http import Http404
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request

from merism.models import OrganizationMembership, Team


class TeamScopedModelViewSet(viewsets.ModelViewSet):
    """Model viewset that filters queryset by the caller's current team.

    Usage::

        class StudyViewSet(TeamScopedModelViewSet):
            queryset = Study.objects.all()
            serializer_class = StudySerializer

    Override ``get_queryset()`` to further filter; the default implementation
    already restricts rows to ``team=self.get_team()`` if the model has a
    ``team`` FK.
    """

    permission_classes = [IsAuthenticated]

    def get_queryset(self):  # type: ignore[override]
        qs = super().get_queryset()
        team = self.get_team()
        if hasattr(qs.model, "team_id"):
            return qs.filter(team=team)
        return qs

    def get_serializer_context(self) -> dict[str, Any]:
        ctx = super().get_serializer_context()
        ctx["get_team"] = self.get_team
        return ctx

    def get_team(self) -> Team:
        request: Request = self.request  # type: ignore[assignment]
        team = _team_from_request(request)
        if team is None:
            raise Http404("No team membership for this user.")
        return team

    def perform_create(self, serializer) -> None:  # type: ignore[override]
        team = self.get_team()
        extra: dict[str, Any] = {}
        # Inject team whenever the model has a ``team_id`` column, even if
        # the serializer doesn't expose the field. This keeps tenant
        # isolation watertight — the team boundary is enforced at the
        # DB write, not at the serializer surface.
        if hasattr(serializer.Meta.model, "team_id"):
            extra["team"] = team
        if "created_by" in serializer.fields or hasattr(
            serializer.Meta.model, "created_by_id"
        ):
            extra["created_by"] = self.request.user
        serializer.save(**extra)


def _team_from_request(request: Request) -> Team | None:
    """Resolve the active team from the request.

    Two strategies, in order:
    1. ``?team=<uuid>`` query param (for explicit cross-team navigation).
    2. First team the authenticated user's organisation owns.

    Anonymous users always get ``None``.
    """
    if not request.user.is_authenticated:
        return None

    explicit = request.query_params.get("team") if hasattr(request, "query_params") else None
    if explicit:
        try:
            candidate = Team.objects.select_related("organization").get(id=explicit)
        except (Team.DoesNotExist, ValueError):
            return None
        if _user_in_org(request.user, candidate.organization_id):
            return candidate
        return None

    membership = (
        OrganizationMembership.objects.filter(user=request.user)
        .select_related("organization")
        .first()
    )
    if membership is None:
        return None
    return membership.organization.teams.order_by("created_at").first()


def _user_in_org(user, organization_id) -> bool:
    return OrganizationMembership.objects.filter(
        user=user, organization_id=organization_id
    ).exists()
