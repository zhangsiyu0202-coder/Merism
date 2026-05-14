"""Link click and share tracking models.

Inspired by:
- Dub.co: per-click event with identity_hash, geo, device, referer, trigger
- pinax-referrals: session_key + ip + http_referrer + action per response
- viral queue: referring → referred relationship table

Design decisions:
- ``LinkClick`` records every resolved link hit (deduplicated per identity_hash
  within 1 hour). Carries IP hash (not raw IP for PIPL), UA, referer, UTM,
  and optional upstream referrer_participation for chain tracking.
- ``LinkShareEvent`` records copy/paste/forward actions so we can trace
  how a link propagates (who shared it to whom).
- ``StudyLink.clicks`` counter is a cache updated atomically via F() on
  each recorded click — avoids COUNT(*) on hot path.
"""

from __future__ import annotations

import hashlib
import uuid

from django.db import models

from merism.models.interview import Participation
from merism.models.study import StudyLink
from merism.models.team import Team, TimestampedModel


def _identity_hash(ip: str, user_agent: str) -> str:
    """SHA-256 hash of IP + UA for deduplication without storing raw IP."""
    raw = f"{ip.strip()}:{user_agent.strip()}".encode()
    return hashlib.sha256(raw).hexdigest()[:32]


class LinkClick(TimestampedModel):
    """One recorded click on a StudyLink.

    Deduplicated: same identity_hash + study_link within 1 hour = skip.
    """

    class Trigger(models.TextChoices):
        LINK = "link"
        QR = "qr"
        DEEPLINK = "deeplink"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="link_clicks")
    study_link = models.ForeignKey(
        StudyLink, on_delete=models.CASCADE, related_name="click_events"
    )
    # Identity (hashed for privacy)
    identity_hash = models.CharField(max_length=32, db_index=True)
    # Optional binding to a participation (set after resolve)
    participation = models.ForeignKey(
        Participation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="link_clicks",
    )
    trace_id = models.UUIDField(default=uuid.uuid4, db_index=True)

    # Request context
    ip_hash = models.CharField(max_length=64, blank=True, default="")
    user_agent = models.TextField(blank=True, default="")
    referer = models.CharField(max_length=512, blank=True, default="")
    referer_url = models.URLField(max_length=1024, blank=True, default="")

    # UTM parameters (captured from query string)
    utm_source = models.CharField(max_length=200, blank=True, default="")
    utm_medium = models.CharField(max_length=200, blank=True, default="")
    utm_campaign = models.CharField(max_length=200, blank=True, default="")
    utm_term = models.CharField(max_length=200, blank=True, default="")
    utm_content = models.CharField(max_length=200, blank=True, default="")

    # Device info (parsed from UA)
    device_type = models.CharField(max_length=32, blank=True, default="")
    browser = models.CharField(max_length=64, blank=True, default="")
    os = models.CharField(max_length=64, blank=True, default="")

    # Geo (from IP lookup if available)
    country = models.CharField(max_length=4, blank=True, default="")

    # Trigger type
    trigger = models.CharField(
        max_length=16, choices=Trigger.choices, default=Trigger.LINK
    )
    is_unique = models.BooleanField(default=True, help_text="First click from this identity_hash on this link.")

    # Upstream tracking: who referred this click?
    # If the clicker arrived via a shared link from another participant,
    # this points to that participant's Participation.
    referrer_participation = models.ForeignKey(
        Participation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="downstream_clicks",
    )

    class Meta:
        db_table = "merism_link_click"
        indexes = [
            models.Index(
                fields=["study_link", "-created_at"],
                name="merism_lc_link_recent_idx",
            ),
            models.Index(
                fields=["study_link", "identity_hash"],
                name="merism_lc_dedup_idx",
            ),
            models.Index(fields=["trace_id"], name="merism_lc_trace_idx"),
            models.Index(fields=["team", "-created_at"], name="merism_lc_team_recent_idx"),
        ]

    def __str__(self) -> str:
        return f"LinkClick({self.study_link_id}, {self.trigger})"


class LinkShareEvent(TimestampedModel):
    """Records when a participant copies/shares a link.

    This enables upstream/downstream chain tracking:
    - sharer_participation: who shared the link
    - recipient_hash: who received it (hashed identifier)
    - When the recipient clicks, their LinkClick.referrer_participation
      points back to sharer_participation.
    """

    class Action(models.TextChoices):
        COPY = "copy"
        SHARE_API = "share_api"  # Web Share API
        FORWARD = "forward"  # IM forward

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="link_share_events")
    study_link = models.ForeignKey(
        StudyLink, on_delete=models.CASCADE, related_name="share_events"
    )
    action = models.CharField(max_length=16, choices=Action.choices, default=Action.COPY)
    # Who shared
    sharer_participation = models.ForeignKey(
        Participation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="share_events",
    )
    trace_id = models.UUIDField(default=uuid.uuid4, db_index=True)

    class Meta:
        db_table = "merism_link_share_event"
        indexes = [
            models.Index(
                fields=["study_link", "-created_at"],
                name="merism_lse_link_recent_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"LinkShareEvent({self.action}, link={self.study_link_id})"
