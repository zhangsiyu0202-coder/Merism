"""InboxItem — researcher-facing notifications.

Every notable event on the platform (session completed, insight ready,
study auto-closed) writes an InboxItem row. The researcher's Inbox
surface reads these ordered by created_at desc.

Design
------
- **Dedup via unique_together** ``(team, kind, ref_kind, ref_id)``.
  Double signal fires collapse to a single row. If a value needs to
  change over time, use ``update_or_create`` with the unique tuple.
- **team scope**: Inbox is team-global; every research workspace member
  sees the same items. Individual user read-state is layered on top
  via the separate ``read_by`` JSON (list of user_ids).
- **ref**: pointer to the underlying entity (session id, insight id,
  study id). Kept loose (CharField) so we don't need N-to-N FKs.
- **payload**: small JSON blob with display data (study name, excerpt,
  status tag) — lets the UI render without extra fetches.
"""

from __future__ import annotations

import uuid

from django.db import models

from merism.models.team import Team


class InboxItem(models.Model):
    class Kind(models.TextChoices):
        SESSION_COMPLETED = "session_completed"
        INSIGHT_READY = "insight_ready"
        STUDY_COMPLETED = "study_completed"
        STUDY_STUCK = "study_stuck"  # e.g. no sessions in N days

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="inbox_items")
    kind = models.CharField(max_length=32, choices=Kind.choices)
    ref_kind = models.CharField(max_length=32)
    ref_id = models.CharField(max_length=64, db_index=True)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    read_by = models.JSONField(default=list, blank=True)  # list[str] user ids
    trace_id = models.UUIDField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "merism_inbox_item"
        unique_together = [("team", "kind", "ref_kind", "ref_id")]
        indexes = [
            models.Index(fields=["team", "-created_at"]),
            models.Index(fields=["team", "kind"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover
        return f"InboxItem({self.kind}, ref={self.ref_id[:8]})"
