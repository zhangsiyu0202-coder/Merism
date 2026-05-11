"""Per-recipient invitation model.

``StudyLink`` gives a Study one public URL (``/i/<slug>``). When a
researcher sends a broadcast to a list of real people, each recipient
should receive a **personal** URL that binds their delivery to the
eventual Participation. That binding lives on ``Invitation``.

Why per-recipient tokens
------------------------
- PIPL/GDPR: closed-audience studies require "we invited this person"
  provable from the row.
- Quota fairness: without a token, a forwarded link allows non-invited
  people to consume slots. With a token, each URL is single-use.
- Funnel analytics: ``delivered_at → accepted_at`` is the open-rate
  signal per channel.

The token is 128-bit random (URL-safe base64, 22 chars). Presence in
the URL's ``?t=`` param is verified by ``/i/<slug>/`` before creating a
Participation. When ``StudyLink.require_invitation = False`` the flow
is still open and no token is required — that's the default so existing
studies don't break.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid

from django.db import models

from merism.models.interview import Participation
from merism.models.study import StudyLink
from merism.models.team import Team


def _new_token() -> str:
    """22-char URL-safe random token (≈ 128 bits entropy)."""
    return secrets.token_urlsafe(16)


def hash_recipient(address: str) -> str:
    """SHA-256 the address so we don't store emails/phones in plaintext."""
    return hashlib.sha256(address.strip().lower().encode("utf-8")).hexdigest()


class Invitation(models.Model):
    """One invited recipient, bound to a StudyLink + optional Participation."""

    class Status(models.TextChoices):
        PENDING = "pending"
        DELIVERED = "delivered"
        ACCEPTED = "accepted"
        EXPIRED = "expired"
        REVOKED = "revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="invitations")
    study_link = models.ForeignKey(
        StudyLink, on_delete=models.CASCADE, related_name="invitations"
    )
    recipient_hash = models.CharField(max_length=64, db_index=True)
    recipient_display = models.CharField(max_length=200, blank=True, default="")
    token = models.CharField(max_length=32, unique=True, default=_new_token)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    trace_id = models.UUIDField(default=uuid.uuid4, db_index=True, editable=False)
    delivered_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    participation = models.ForeignKey(
        Participation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invitations",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "merism_invitation"
        indexes = [
            models.Index(fields=["study_link", "status"]),
            models.Index(fields=["recipient_hash"]),
        ]
        # One outstanding invite per recipient per link (re-send is an UPDATE).
        unique_together = [("study_link", "recipient_hash")]

    def __str__(self) -> str:  # pragma: no cover
        return f"Invitation({self.status}, link={self.study_link_id})"
