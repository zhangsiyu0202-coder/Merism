"""Recruitment-domain models (per spec ``cowagent-im-recruitment``).

- ``ChannelConfig``          Req 1: per-team IM channel credentials (Fernet-encrypted).
- ``MessageTemplate``        Req 2: invite templates with {{placeholder}} rendering.
- ``RecruitmentBroadcast``   Req 3: a batch send targeting one channel.
- ``DeliveryRecord``         Req 4: per-recipient delivery outcome (pending/sent/failed/delivered).
- ``ChannelHealthCheck``     Req 5: periodic health-check probe results.
"""

from __future__ import annotations

import uuid

from django.db import models

from merism.models.study import Study, StudyLink
from merism.models.team import Team, TimestampedModel


class ChannelConfig(TimestampedModel):
    """Per-team IM channel credentials.

    ``credentials_encrypted`` holds a Fernet-encrypted blob produced by
    :func:`merism.recruitment.crypto.encrypt_credentials`. Plaintext
    credentials must never touch the DB.

    Channel types mirror the CowAgent adapter family:
      - feishu       Lark / Feishu native app
      - wecom        WeCom native app (workspace)
      - wecom_bot    WeCom webhook bot
      - qq_group     QQ group bot (open-platform app)
      - qq_guild     QQ guild (frequency) app
    """

    class ChannelType(models.TextChoices):
        FEISHU = "feishu"
        WECOM = "wecom"
        WECOM_BOT = "wecom_bot"
        QQ_GROUP = "qq_group"
        QQ_GUILD = "qq_guild"
        # Email (SMTP or MCP-backed). Distinct from IM channels in that
        # recipient_id is an RFC-5322 address rather than an IM user/group
        # id. The transport is abstracted so an MCP-based sender (e.g.
        # resend/mcp-send-email) can be swapped in without changing the
        # adapter public surface.
        EMAIL = "email"

    class Status(models.TextChoices):
        ACTIVE = "active"
        INACTIVE = "inactive"
        ERROR = "error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="channel_configs")
    channel_type = models.CharField(max_length=16, choices=ChannelType.choices)
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.INACTIVE)
    # Fernet-encrypted blob. Never log or echo raw.
    credentials_encrypted = models.BinaryField(null=True, blank=True)
    # Health-check metadata (updated by the beat task every 30 min).
    last_healthy_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    consecutive_failures = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "merism_channel_config"
        indexes = [
            models.Index(fields=["team", "channel_type"], name="merism_cc_team_type_idx"),
            models.Index(fields=["status"], name="merism_cc_status_idx"),
        ]

    def __str__(self) -> str:
        return f"ChannelConfig({self.channel_type}, {self.name})"


class ChannelTarget(TimestampedModel):
    """A saved outbound destination bound to one channel configuration.

    First version supports only group targets. We keep the model generic so
    later we can support direct user outreach without reshaping broadcasts.
    """

    class RecipientKind(models.TextChoices):
        GROUP = "group"
        USER = "user"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="channel_targets")
    channel = models.ForeignKey(
        ChannelConfig, on_delete=models.CASCADE, related_name="targets"
    )
    name = models.CharField(max_length=200)
    recipient_id = models.CharField(max_length=200)
    recipient_kind = models.CharField(
        max_length=16,
        choices=RecipientKind.choices,
        default=RecipientKind.GROUP,
    )
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "merism_channel_target"
        indexes = [
            models.Index(fields=["team", "is_active"], name="merism_ct_team_active_idx"),
            models.Index(fields=["channel", "is_default"], name="merism_ct_channel_default_idx"),
        ]

    def __str__(self) -> str:
        return f"ChannelTarget({self.name}, {self.channel_id})"


class MessageTemplate(TimestampedModel):
    """Invite message template with {{placeholder}} rendering.

    Required placeholders: ``{{study_name}}``, ``{{study_link}}``.
    Other placeholders like ``{{name}}``, ``{{deadline}}``, ``{{reward}}``,
    ``{{researcher_name}}`` are optional.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, null=True, blank=True, related_name="message_templates"
    )
    name = models.CharField(max_length=200)
    channel_type = models.CharField(max_length=16, choices=ChannelConfig.ChannelType.choices)
    content = models.TextField()
    is_system = models.BooleanField(default=False, help_text="Shipped by Merism, not team-owned.")

    class Meta:
        db_table = "merism_message_template"
        indexes = [
            models.Index(fields=["team", "channel_type"], name="merism_mt_team_type_idx"),
            models.Index(fields=["is_system"], name="merism_mt_system_idx"),
        ]

    def __str__(self) -> str:
        return f"MessageTemplate({self.name}, {self.channel_type})"


class RecruitmentBroadcast(TimestampedModel):
    """One broadcast task: send invites to a list of recipients via one channel."""

    class Status(models.TextChoices):
        DRAFT = "draft"
        APPROVED = "approved"
        SENDING = "sending"
        COMPLETED = "completed"
        PARTIALLY_FAILED = "partially_failed"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="recruitment_broadcasts")
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="broadcasts")
    study_link = models.ForeignKey(
        StudyLink,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="broadcasts",
    )
    channel = models.ForeignKey(ChannelConfig, on_delete=models.CASCADE, related_name="broadcasts")
    template = models.ForeignKey(MessageTemplate, on_delete=models.PROTECT, related_name="broadcasts")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    # Approved content snapshot at the moment of broadcast-approve click, so
    # the task uses the exact text that was approved (template may change later).
    approved_snapshot = models.JSONField(default=dict, blank=True)
    # {"total": N, "sent": N, "failed": N, "delivered": N}
    counters = models.JSONField(default=dict, blank=True)
    retry_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "merism_recruitment_broadcast"
        indexes = [
            models.Index(fields=["team", "status"], name="merism_rb_team_status_idx"),
            models.Index(fields=["study"], name="merism_rb_study_idx"),
        ]

    def __str__(self) -> str:
        return f"RecruitmentBroadcast({self.status}, study={self.study_id})"


class DeliveryRecord(TimestampedModel):
    """Per-recipient delivery outcome."""

    class Status(models.TextChoices):
        PENDING = "pending"
        SENT = "sent"
        DELIVERED = "delivered"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="delivery_records")
    broadcast = models.ForeignKey(
        RecruitmentBroadcast, on_delete=models.CASCADE, related_name="deliveries"
    )
    recipient_id = models.CharField(max_length=200, db_index=True)
    recipient_kind = models.CharField(max_length=16, default="user")  # user | group
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    message_id = models.CharField(max_length=200, blank=True, default="")
    error = models.TextField(blank=True, default="")
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    trace_id = models.UUIDField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "merism_delivery_record"
        indexes = [
            models.Index(fields=["broadcast", "status"], name="merism_dr_bcast_status_idx"),
            models.Index(fields=["recipient_id"], name="merism_dr_rcpt_idx"),
        ]

    def __str__(self) -> str:
        return f"DeliveryRecord({self.status}, to={self.recipient_id})"


class ChannelHealthCheck(TimestampedModel):
    """Append-only log of health-check probe results. Recent N rows determine
    ``ChannelConfig.consecutive_failures``."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="channel_health_checks")
    channel = models.ForeignKey(
        ChannelConfig, on_delete=models.CASCADE, related_name="health_checks"
    )
    ok = models.BooleanField()
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        db_table = "merism_channel_health_check"
        indexes = [
            models.Index(fields=["channel", "-created_at"], name="merism_chc_recent_idx"),
        ]
