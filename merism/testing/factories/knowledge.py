"""Knowledge-domain factories.

KnowledgeChunk / KnowledgeDocument for RAG. TeamResearchKnowledgeBase (L1,
team-wide) and StudyKnowledgeBase (L2, study-scoped).
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any


def make_team_kb(
    *,
    team_id: int = 1,
    name: str = "Team Research KB",
    stub: bool = True,
) -> SimpleNamespace:
    """Build a TeamResearchKnowledgeBase (L1)."""
    if not stub:
        raise NotImplementedError("make_team_kb(stub=False) requires Phase C1")
    return SimpleNamespace(
        id=uuid.uuid4(),
        pk=uuid.uuid4(),
        team_id=team_id,
        name=name,
    )


def make_study_kb(
    study: SimpleNamespace,
    *,
    name: str | None = None,
    stub: bool = True,
) -> SimpleNamespace:
    """Build a StudyKnowledgeBase (L2)."""
    if not stub:
        raise NotImplementedError("make_study_kb(stub=False) requires Phase C1")
    return SimpleNamespace(
        id=uuid.uuid4(),
        pk=uuid.uuid4(),
        study=study,
        study_id=study.id,
        team_id=study.team_id,
        name=name or f"KB for {study.name}",
    )


def make_knowledge_document(
    *,
    id: str | uuid.UUID | None = None,
    title: str = "Session transcript",
    content: str = "",
    source_type: str = "session",
    source_id: str = "",
    status: str = "indexed",
    team_id: int = 1,
    study_id: uuid.UUID | None = None,
    embedding: list[float] | None = None,
    stub: bool = True,
    **extra: Any,
) -> SimpleNamespace:
    """Build a KnowledgeDocument (legacy Phase-0 L2 unit)."""
    if not stub:
        raise NotImplementedError("make_knowledge_document(stub=False) requires Phase C1")
    doc_id = id if id is not None else uuid.uuid4()
    return SimpleNamespace(
        id=doc_id,
        pk=doc_id,
        title=title,
        content=content,
        source_type=source_type,
        source_id=source_id,
        status=status,
        team_id=team_id,
        study_id=study_id,
        embedding=embedding,
        **extra,
    )


def make_knowledge_chunk(
    source_document: SimpleNamespace | None = None,
    *,
    id: str | uuid.UUID | None = None,
    content: str = "",
    team_id: int = 1,
    chunk_index: int = 0,
    embedding: list[float] | None = None,
    distance: float = 0.0,
    # Convenience: let callers describe the source document inline without
    # constructing a separate object.
    document_title: str | None = None,
    document_source_type: str | None = None,
    document_source_id: str | None = None,
    stub: bool = True,
    **extra: Any,
) -> SimpleNamespace:
    """Build a KnowledgeChunk (new model for chunked RAG retrieval).

    If ``source_document`` is omitted, a fresh stub document is created. The
    ``document_*`` convenience kwargs shape the inline document without
    building one by hand.
    """
    if not stub:
        raise NotImplementedError("make_knowledge_chunk(stub=False) requires Phase C1")
    if source_document is None:
        source_document = make_knowledge_document(
            team_id=team_id,
            title=document_title if document_title is not None else "Session transcript",
            source_type=document_source_type if document_source_type is not None else "session",
            source_id=document_source_id if document_source_id is not None else "",
            stub=True,
        )

    chunk_id = id if id is not None else uuid.uuid4()
    chunk = SimpleNamespace(
        id=chunk_id,
        pk=chunk_id,
        content=content,
        team_id=team_id,
        chunk_index=chunk_index,
        embedding=embedding,
        distance=distance,
        source_document=source_document,
        source_document_id=source_document.id,
        **extra,
    )
    return chunk
