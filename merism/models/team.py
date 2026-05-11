"""Core model mixins and the ``Team`` tenant model.

Every Merism table is prefixed ``merism_`` and carries ``team_id`` (either as
a FK to ``merism.Team`` or a ``BigIntegerField`` for models that may split
into a separate DB later). This file defines:

- :class:`Organization` — top-level tenant; owns Teams.
- :class:`Team`         — the unit of tenant isolation. Every research study
  and its data belong to exactly one Team.
- :class:`TimestampedModel` mixin — ``created_at`` / ``updated_at`` fields.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.conf import settings
from django.db import models


class TimestampedModel(models.Model):
    """Abstract base: ``created_at`` / ``updated_at`` auto-populated."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(TimestampedModel):
    """Abstract base: UUID primary key."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class Organization(TimestampedModel):
    """Top-level tenant. A team always belongs to one organization."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, max_length=64)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="OrganizationMembership",
        related_name="merism_organizations",
    )

    class Meta:
        db_table = "merism_organization"

    def __str__(self) -> str:
        return f"Organization({self.name})"


class OrganizationMembership(TimestampedModel):
    """User ↔ Organization membership with a role."""

    class Role(models.TextChoices):
        OWNER = "owner"
        ADMIN = "admin"
        MEMBER = "member"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="merism_org_memberships",
    )
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MEMBER)

    class Meta:
        db_table = "merism_organization_membership"
        unique_together = [("organization", "user")]


class Team(TimestampedModel):
    """Tenant-isolation boundary. Everything research-related FKs to Team.

    Per spec (AGENTS Rule 3): every tenant-data model must carry ``team_id``.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="teams"
    )
    # Feature flags / per-team config go into this JSON bag. Prefer adding
    # dedicated columns when a flag graduates to a first-class setting.
    config = models.JSONField(default=dict, blank=True)

    # Teams are the unit that research data belongs to — no per-team database
    # split yet, but the design allows it via the ``team_id`` convention.

    class Meta:
        db_table = "merism_team"
        indexes = [
            models.Index(fields=["organization"], name="merism_team_org_idx"),
        ]

    def __str__(self) -> str:
        return f"Team({self.name})"


def team_id_field(**kwargs: Any) -> models.BigIntegerField:
    """Alternative to ``ForeignKey('merism.Team')`` for models that may live
    in a separate DB (e.g., high-volume event-log style tables). Returns a
    ``BigIntegerField`` with an index, matching the FK column shape.
    """
    kwargs.setdefault("db_index", True)
    return models.BigIntegerField(**kwargs)
