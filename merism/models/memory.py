"""MEM AI memory models.

These hold persistent state for the Merism AI agent across conversations:

- :class:`Conversation` — one chat thread (Ask Merism or sidebar Q&A).
- :class:`AgentMemory`  — semantic-searchable memory (user preferences,
  domain facts). Retrieved via the ``manage_memories`` tool.
- :class:`CoreMemory`   — curated org- / team- / user-level facts the agent
  always loads into its context (e.g., "this team is a fintech startup").
- :class:`AskArtifact`  — structured output generated during a conversation
  (quote cards, comparison tables, theme maps, etc.).
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from merism.models.team import Team, TimestampedModel


def _short_id(length: int = 10) -> str:
    """Return a compact public identifier for Ask artifacts."""
    return uuid.uuid4().hex[:length]


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
    messages = models.JSONField(default=list, blank=True, help_text="Persisted chat messages [{role, content, tool_calls?}]")
    study = models.ForeignKey("merism.Study", on_delete=models.SET_NULL, null=True, blank=True, related_name="ai_conversations", help_text="Context study if opened from a study page")

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
    messages = models.JSONField(default=list, blank=True, help_text="Persisted chat messages [{role, content, tool_calls?}]")
    study = models.ForeignKey("merism.Study", on_delete=models.SET_NULL, null=True, blank=True, related_name="agent_memories_by_study", help_text="Context study if opened from a study page")
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


class AskArtifact(TimestampedModel):
    """Structured output generated by Merism AI during a conversation.

    Each artifact is a typed, renderable block (quote card, comparison table,
    theme map, etc.) that the frontend can display inline or in a gallery.
    """

    class Type(models.TextChoices):
        RESEARCH_QUOTE = "research_quote", "Research Quote"
        COMPARISON_TABLE = "comparison_table", "Comparison Table"
        THEME_MAP = "theme_map", "Theme Map"
        INSIGHT_CARD = "insight_card", "Insight Card"
        STUDY_SUMMARY = "study_summary", "Study Summary"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    short_id = models.CharField(max_length=16, unique=True, db_index=True, default=_short_id)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="ask_artifacts")
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="artifacts",
        null=True,
        blank=True,
    )
    type = models.CharField(max_length=32, choices=Type.choices)
    name = models.CharField(max_length=400, blank=True, default="")
    data = models.JSONField(default=dict)

    class Meta:
        db_table = "merism_ask_artifact"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["team", "-created_at"], name="merism_artifact_team_idx"),
            models.Index(fields=["conversation"], name="merism_artifact_conv_idx"),
        ]

    def __str__(self) -> str:
        return f"AskArtifact({self.type}: {self.name or self.short_id})"
