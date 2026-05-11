"""Post-session processing orchestrator.

Celery enqueues :func:`process_completed_session` via the Django
``post_save`` signal. This module chains together the full Sprint 2+3
pipeline:

    transcript polish (Sprint 2)
        ↓
    codebook seed (Sprint 3, idempotent, once per study)
        ↓
    quote extraction (Sprint 3)
        ↓
    quote tagging (Sprint 3)
        ↓
    RAG indexing (Sprint 3)
        ↓
    SessionInsight generation (Sprint 3)

Every stage is idempotent on its own, so partial failures and retries
are safe.
"""

from __future__ import annotations

import logging
from uuid import UUID

from asgiref.sync import sync_to_async

from merism.conductor.llm_polish import polish_session_turns
from merism.conductor.transcript_helpers import has_clean_transcript
from merism.knowledge.indexer import index_session_quotes
from merism.memai.agents.codebook_seeder import seed_codebook
from merism.memai.agents.quote_extractor import extract_quotes
from merism.memai.agents.quote_tagger import (
    promote_inductive_suggestions,
    tag_quotes_for_session,
)
from merism.memai.agents.session_insight_generator import generate_insight
from merism.models import InterviewSession

logger = logging.getLogger(__name__)


async def process_session_transcripts(session_id: str | UUID) -> dict[str, int]:
    """Full post-session pipeline.

    Returns counters dict:
        {turn_count, polished, quotes, tagged, indexed, insight_created}.
    """
    session = await _aget_session(session_id)
    if session is None:
        logger.warning("post_session.session_missing", extra={"session_id": str(session_id)})
        return {"turn_count": 0, "polished": 0, "quotes": 0, "tagged": 0, "indexed": 0, "insight_created": 0}

    counters = {
        "turn_count": 0,
        "polished": 0,
        "quotes": 0,
        "tagged": 0,
        "indexed": 0,
        "insight_created": 0,
    }

    # ── 1. Transcript polish (Sprint 2) ──
    raw_transcript = list(session.transcript or [])
    counters["turn_count"] = len(raw_transcript)

    if not has_clean_transcript(raw_transcript):
        polished = await polish_session_turns(raw_transcript)
        session.transcript = polished
        await _asave_transcript(session)
        counters["polished"] = sum(
            1
            for t in polished
            if t.get("role") == "participant" and t.get("text_clean")
        )
    else:
        logger.info(
            "post_session.polish_skipped_already_clean",
            extra={"session_id": str(session.id)},
        )

    # ── 2. Codebook seed (once per study, idempotent) ──
    await seed_codebook(session.study)

    # ── 3. Quote extraction ──
    quotes = await extract_quotes(session)
    counters["quotes"] = len(quotes)

    if not quotes:
        logger.info(
            "post_session.no_quotes_extracted",
            extra={"session_id": str(session.id)},
        )
        return counters

    # ── 4. Tagging (deductive + inductive) ──
    await tag_quotes_for_session(quotes, session.study)
    counters["tagged"] = len(quotes)

    # Opportunistic codebook growth: if recurring inductive suggestions
    # have built up, merge them into the study codebook.
    await promote_inductive_suggestions(session.study, min_occurrences=2)

    # ── 5. RAG indexing ──
    # Refresh the quotes to pick up freshly-written tags.
    quotes = await _arefresh_quotes(quotes)
    counters["indexed"] = await index_session_quotes(session, quotes)

    # ── 6. SessionInsight generation ──
    insight = await generate_insight(session, quotes)
    counters["insight_created"] = 1 if insight is not None else 0

    logger.info(
        "post_session.pipeline_done",
        extra={"session_id": str(session.id), **counters},
    )
    return counters


# ── DB helpers ──

@sync_to_async
def _aget_session(session_id: str | UUID) -> InterviewSession | None:
    try:
        return InterviewSession.objects.select_related("study", "guide", "team").get(
            id=session_id
        )
    except InterviewSession.DoesNotExist:
        return None


@sync_to_async
def _arefresh_quotes(quotes: list) -> list:
    # Re-read quotes so tags persisted by the tagger are visible to the
    # indexer. Uses a fresh queryset to avoid stale in-memory state.
    from merism.models import SessionQuote

    ids = [q.id for q in quotes]
    return list(SessionQuote.objects.filter(id__in=ids))


async def _asave_transcript(session: InterviewSession) -> None:
    asave = getattr(session, "asave", None)
    if callable(asave):
        await asave(update_fields=["transcript", "updated_at"])
    else:  # pragma: no cover
        await sync_to_async(session.save)(update_fields=["transcript", "updated_at"])
