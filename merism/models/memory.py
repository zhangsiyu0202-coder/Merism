"""MEM AI memory models.

These hold persistent state for the Merism AI agent across conversations:

- :class:`Conversation` — one chat thread (Ask Merism or sidebar Q&A).
- :class:`AgentMemory`  — semantic-searchable memory (user preferences,
  domain facts). Retrieved via the ``manage_memories`` tool.
- :class:`CoreMemory`   — curated org- / team- / user-level facts the agent
  always loads into its context (e.g., "this team is a fintech startup").
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from merism.models.team import Team, TimestampedModel


class Conversation(TimestampedModel):
    """One chat thread between a user and Merism AI."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="conversations")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="merism_conversations",
    )
    title = models.CharField(max_length=300, blank=True, default="")
    # Messages persisted via LangGraph checkpointer — the Conversation row
    # itself is the stable pointer for UI / billing.
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "merism_conversation"
        indexes = [
            models.Index(fields=["team", "user", "-updated_at"], name="merism_conv_recent_idx"),
        ]

    def __str__(self) -> str:
        return f"Conversation({self.title or self.id})"


class AgentMemory(TimestampedModel):
    """Semantic memory used by the ``manage_memories`` tool. Embedded for
    retrieval. Scoped to the team; optionally attributable to a user."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="agent_memories")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merism_agent_memories",
    )
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    # Soft-delete flag — semantic retrieval filters out deleted rows but keeps
    # them for audit trail.
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = "merism_agent_memory"
        indexes = [
            models.Index(fields=["team", "is_deleted"], name="merism_am_team_active_idx"),
            models.Index(fields=["user"], name="merism_am_user_idx"),
        ]

    def __str__(self) -> str:
        return f"AgentMemory({self.content[:40]})"


class CoreMemory(TimestampedModel):
    """Curated org/team/user-level facts the agent always sees.

    Kept intentionally small — bloat here hurts every prompt. Target < 500
    tokens combined per conversation.
    """

    class Scope(models.TextChoices):
        ORGANIZATION = "organization"
        TEAM = "team"
        USER = "user"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="core_memories")
    scope = models.CharField(max_length=16, choices=Scope.choices, default=Scope.TEAM)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="merism_core_memories",
    )
    # Human-editable blob. No embeddings — this is loaded verbatim into context.
    content = models.TextField(blank=True, default="")

    class Meta:
        db_table = "merism_core_memory"
        indexes = [
            models.Index(fields=["team", "scope"], name="merism_cm_team_scope_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["team", "scope", "user"],
                name="merism_cm_unique_scope",
            ),
        ]

    def __str__(self) -> str:
        return f"CoreMemory({self.scope})"
