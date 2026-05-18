"""Auto-provision org + team for new users on signup."""

from __future__ import annotations

from allauth.account.signals import user_signed_up
from django.dispatch import receiver

from merism.models import OrganizationMembership
from merism.models.team import Organization, Team


@receiver(user_signed_up)
def provision_org_and_team(request, user, **kwargs) -> None:
    """Create a default org + team for newly registered users."""
    if OrganizationMembership.objects.filter(user=user).exists():
        return

    name = user.email.split("@")[0].title()
    org = Organization.objects.create(name=f"{name}'s Workspace", slug=f"{name.lower()}-ws")
    Team.objects.create(name="Default", organization=org)
    OrganizationMembership.objects.create(user=user, organization=org)
