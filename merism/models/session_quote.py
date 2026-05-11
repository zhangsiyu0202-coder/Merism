"""SessionQuote — the smallest analyzable unit of qualitative data.

One SessionQuote = one notable passage extracted from a session's clean
transcript. Quotes are the source-of-truth for every downstream artifact:

- Tags / codes attach to quotes (not to whole turns or sessions).
- KnowledgeChunk rows embed quote text for RAG search.
- SessionInsight.highlights reference quote ids.
- Report QuoteBlocks cite quote ids.
- Affinity map / treemap visualise quote clusters.

Per Braun & Clarke, a "code" is the smallest analytical label; in our
pipeline a quote is the smallest *text segment* that a code can attach
to. We denormalise ``study_id`` so study-scoped queries don't have to
hop through session → study for every row.
"""

from __future__ import annotations

import uuid

from django.db import models

from merism.models.interview import InterviewSession
from merism.models.study import Study
from merism.models.team import Team, TimestampedModel


class SessionQuote(TimestampedModel):
    """A high-value extracted quote from a completed session's transcript."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="session_quotes")
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="session_quotes")
    session = models.ForeignKey(
        InterviewSession, on_delete=models.CASCADE, related_name="quotes"
    )

    # ── Source location in the transcript ────────────────────────
    text = models.TextField()
    turn_indices = models.JSONField(default=list, blank=True)
    ts_start_ms = models.PositiveIntegerField(default=0)
    ts_end_ms = models.PositiveIntegerField(default=0)
    question_id = models.CharField(max_length=64, blank=True, default="")
    concept_id = models.CharField(max_length=64, blank=True, default="")

    # ── Analysis outputs (populated by tagger) ────────────────────
    # tags JSON shape (by agreement):
    #   {
    #     "deductive": [{"code_id": "...", "confidence": 0.0}],
    #     "inductive_suggestions": [{"code": "...", "rationale": "..."}],
    #     "sentiment": "positive" | "negative" | "neutral" | "mixed",
    #     "action_type": "suggestion" | "complaint" | "praise" | "question" | null
    #   }
    tags = models.JSONField(default=dict, blank=True)

    # 0..1 importance score from the extractor — used to rank quotes in
    # reports / insights / affinity maps.
    importance = models.FloatField(default=0.5)

    # Set when the quote has been indexed into the RAG store (Sprint 3.5).
    # Back-reference to a KnowledgeChunk row; nullable so the indexer is
    # idempotent (extract first, embed later).
    embedded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "merism_session_quote"
        ordering = ["-importance", "ts_start_ms"]
        indexes = [
            models.Index(fields=["team", "study"], name="merism_sq_team_study_idx"),
            models.Index(fields=["session"], name="merism_sq_session_idx"),
            models.Index(fields=["question_id"], name="merism_sq_question_idx"),
            models.Index(fields=["concept_id"], name="merism_sq_concept_idx"),
        ]

    def __str__(self) -> str:
        snippet = self.text[:40].replace("\n", " ")
        return f"SessionQuote({snippet}…)"
