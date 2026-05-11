"""Knowledge / RAG models.

Per ``merism-platform`` Req 19 (cross-study Knowledge Explore):
- ``TeamResearchKnowledgeBase`` — L1, team-wide. One row per Team.
- ``StudyKnowledgeBase``        — L2, per-study. One row per Study.
- ``KnowledgeDocument``         — whole indexed content unit (a session
  transcript, a report, a note).
- ``KnowledgeChunk``            — chunked retrieval unit with pgvector
  embedding. Hybrid search (BM25 + dense) happens over these.

Embedding dimension is 1536 (DeepSeek / OpenAI text-embedding-3-small). Override
per team via ``TeamResearchKnowledgeBase.embedding_config`` if needed.
"""

from __future__ import annotations

import uuid

from django.db import models

try:
    from pgvector.django import VectorField
except ImportError:  # pragma: no cover - dev only
    VectorField = None  # type: ignore[assignment,misc]

from merism.models.interview import InterviewSession
from merism.models.study import Study
from merism.models.team import Team, TimestampedModel


EMBEDDING_DIM = 1536


class TeamResearchKnowledgeBase(TimestampedModel):
    """L1 — team-wide knowledge base. One row per Team. The retriever uses this
    row's chunks across ALL studies in that team."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.OneToOneField(Team, on_delete=models.CASCADE, related_name="research_kb")
    name = models.CharField(max_length=200, default="Team Research Knowledge Base")
    embedding_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Override embedding model + dimension here.",
    )

    class Meta:
        db_table = "merism_team_research_kb"

    def __str__(self) -> str:
        return f"TeamResearchKB(team={self.team_id})"


class StudyKnowledgeBase(TimestampedModel):
    """L2 — per-study knowledge base. Scopes retrieval to one Study."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="study_kbs")
    study = models.OneToOneField(Study, on_delete=models.CASCADE, related_name="kb")
    name = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        db_table = "merism_study_kb"
        indexes = [
            models.Index(fields=["team", "study"], name="merism_skb_team_study_idx"),
        ]

    def __str__(self) -> str:
        return f"StudyKB(study={self.study_id})"


class KnowledgeDocument(TimestampedModel):
    """Whole indexed content unit. A session transcript, a study report, a
    researcher note, etc. Individual chunks FK back to this row."""

    class SourceType(models.TextChoices):
        SESSION_TRANSCRIPT = "session_transcript"
        STUDY_REPORT = "study_report"
        SESSION_INSIGHT = "session_insight"
        NOTE = "note"

    class Status(models.TextChoices):
        PENDING = "pending"
        INDEXING = "indexing"
        INDEXED = "indexed"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="knowledge_documents")
    study = models.ForeignKey(
        Study,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="knowledge_documents",
    )
    session = models.ForeignKey(
        InterviewSession,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="knowledge_documents",
    )
    title = models.CharField(max_length=300)
    content = models.TextField(blank=True, default="")
    source_type = models.CharField(
        max_length=32, choices=SourceType.choices, default=SourceType.SESSION_TRANSCRIPT
    )
    source_id = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "merism_knowledge_document"
        indexes = [
            models.Index(fields=["team", "source_type"], name="merism_kd_team_src_idx"),
            models.Index(fields=["study"], name="merism_kd_study_idx"),
            models.Index(fields=["status"], name="merism_kd_status_idx"),
        ]

    def __str__(self) -> str:
        return f"KnowledgeDocument({self.source_type}, {self.title[:30]})"


class KnowledgeChunk(TimestampedModel):
    """Chunked RAG retrieval unit with pgvector embedding.

    Hybrid search (BM25 + dense cosine) runs over these. The dense index lives
    on ``embedding`` (pgvector IVF). The lexical index is a Postgres GIN on
    ``content`` via a migration.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="knowledge_chunks")
    document = models.ForeignKey(
        KnowledgeDocument,
        on_delete=models.CASCADE,
        related_name="chunks",
    )
    chunk_index = models.PositiveIntegerField()
    content = models.TextField()
    # Embedding: 1536 floats (pgvector). May be null while embedding is queued.
    embedding = (
        VectorField(dimensions=EMBEDDING_DIM, null=True, blank=True)
        if VectorField is not None
        else models.JSONField(default=list, blank=True)  # sqlite test fallback
    )
    # Distance score filled during retrieval; not persistent on read path but
    # kept on annotated querysets. Leave as a CharField-null hint for tests.
    # (Actual float distance is attached dynamically by the retriever.)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "merism_knowledge_chunk"
        indexes = [
            models.Index(fields=["team"], name="merism_kc_team_idx"),
            models.Index(fields=["document", "chunk_index"], name="merism_kc_doc_order_idx"),
        ]
        unique_together = [("document", "chunk_index")]

    def __str__(self) -> str:
        return f"KnowledgeChunk(doc={self.document_id}, #{self.chunk_index})"
