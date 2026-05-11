"""User-scoped endpoints.

Minimal surface for now — ``/api/users/me/`` returns the authenticated
user along with their active team and organisation. The frontend
``userLogic`` mounts on every authenticated scene and relies on this
endpoint to decide whether to route to ``/login`` vs the app shell.
"""

from __future__ import annotations

from typing import Any

from rest_framework import permissions, serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from merism.models import OrganizationMembership, Team


class _TeamMiniSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    organization = serializers.UUIDField(source="organization_id")


class _OrganizationMiniSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    slug = serializers.SlugField()


class UserMeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    is_superuser = serializers.BooleanField()
    organization = _OrganizationMiniSerializer(allow_null=True)
    team = _TeamMiniSerializer(allow_null=True)


class UserMeView(APIView):
    """``GET /api/users/me/`` — current user + their first active team."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = request.user
        membership = (
            OrganizationMembership.objects.filter(user=user)
            .select_related("organization")
            .first()
        )
        organization = membership.organization if membership else None

        team = None
        if organization is not None:
            team = Team.objects.filter(organization=organization).first()

        payload: dict[str, Any] = {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_superuser": bool(user.is_superuser),
            "organization": organization,
            "team": team,
        }
        return Response(UserMeSerializer(payload).data)
