"""Transcript indexer — embeds interview transcripts into KnowledgeChunk.

Splits transcript into chunks (grouped turns), embeds, and stores for
RAG retrieval. Called incrementally when a session completes or when
new turns are appended.
"""

from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import sync_to_async
from django.utils import timezone

from merism.knowledge.embeddings import embed_batch
from merism.models import InterviewSession, KnowledgeChunk, KnowledgeDocument

logger = logging.getLogger(__name__)

# Group N turns per chunk for better semantic coherence
TURNS_PER_CHUNK = 4


def _chunk_transcript(transcript: list[dict]) -> list[str]:
    """Split transcript into semantic chunks of TURNS_PER_CHUNK turns."""
    chunks = []
    for i in range(0, len(transcript), TURNS_PER_CHUNK):
        group = transcript[i : i + TURNS_PER_CHUNK]
        text = "\n".join(
            f"{'AI' if t.get('role') == 'assistant' else '参与者'}: {t.get('text', '')}"
            for t in group
        )
        if text.strip():
            chunks.append(text)
    return chunks


async def index_session_transcript(session: InterviewSession) -> int:
    """Index a session's transcript into KnowledgeChunk.

    Returns the number of new chunks written. Idempotent — checks
    existing chunk count vs expected and only indexes new content.
    """
    transcript = session.transcript or []
    if not transcript:
        return 0

    chunks = _chunk_transcript(transcript)
    if not chunks:
        return 0

    document = await _get_or_create_document(session)

    # Check how many chunks already indexed
    existing_count = await sync_to_async(
        lambda: KnowledgeChunk.objects.filter(document=document).count()
    )()

    # Only index new chunks (incremental)
    new_chunks = chunks[existing_count:]
    if not new_chunks:
        return 0

    embeddings = await sync_to_async(embed_batch)(new_chunks)

    written = await _persist_chunks(new_chunks, embeddings, document, offset=existing_count, session=session)
    logger.info(
        "knowledge.index_transcript.done",
        extra={"session_id": str(session.id), "new_chunks": written, "total": existing_count + written},
    )
    return written


@sync_to_async
def _get_or_create_document(session: InterviewSession) -> KnowledgeDocument:
    doc, _ = KnowledgeDocument.objects.get_or_create(
        team=session.team,
        study=session.study,
        session=session,
        source_type=KnowledgeDocument.SourceType.SESSION_TRANSCRIPT,
        defaults={
            "title": f"Transcript · {str(session.id)[:8]}",
            "content": "",
            "status": KnowledgeDocument.Status.INDEXED,
            "metadata": {"kind": "transcript"},
        },
    )
    return doc


@sync_to_async
def _persist_chunks(
    chunks: list[str],
    embeddings: list[list[float] | None],
    document: KnowledgeDocument,
    offset: int,
    session: InterviewSession,
) -> int:
    created = 0
    for i, (text, embedding) in enumerate(zip(chunks, embeddings, strict=False)):
        if embedding is None:
            continue
        KnowledgeChunk.objects.create(
            team=session.team,
            document=document,
            chunk_index=offset + i,
            content=text,
            embedding=embedding,
            metadata={
                "session_id": str(session.id),
                "study_id": str(session.study_id),
                "chunk_type": "transcript",
                "turn_range": [offset * TURNS_PER_CHUNK + i * TURNS_PER_CHUNK, offset * TURNS_PER_CHUNK + (i + 1) * TURNS_PER_CHUNK],
            },
        )
        created += 1
    return created
