"""Conductor Celery tasks.

Wraps async domain logic from :mod:`merism.conductor.post_session` in a
sync Celery shim. Mirrors the :mod:`merism.recruitment.tasks` pattern.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from celery import chain, shared_task

from merism.conductor.post_session import process_session_transcripts

logger = logging.getLogger(__name__)


# ── Stage tasks ──────────────────────────────────────────────
# Each stage is idempotent and runs the matching phase of the
# post-session pipeline. Splitting lets Celery Flower / admin observe
# per-stage status and retry failed stages without redoing earlier
# ones. The chain is still kicked off by the same post_save signal.


def _run_async(coro):
    """Sync Celery → async domain shim."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def stage_polish_transcript(self, session_id: str) -> str:
    """Stage 1: polish transcript (idempotent)."""
    from asgiref.sync import sync_to_async
    from merism.conductor.llm_polish import polish_session_turns
    from merism.conductor.transcript_helpers import has_clean_transcript
    from merism.models import InterviewSession

    async def _run():
        @sync_to_async
        def _get():
            return InterviewSession.objects.filter(id=session_id).first()

        session = await _get()
        if session is None or has_clean_transcript(session.transcript or []):
            return
        polished = await polish_session_turns(session.transcript or [])
        session.transcript = polished

        @sync_to_async
        def _save():
            session.save(update_fields=["transcript", "updated_at"])

        await _save()

    try:
        _run_async(_run())
    except Exception as exc:
        logger.exception("post_session.stage_polish_failed")
        raise self.retry(exc=exc)
    return session_id


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def stage_extract_and_tag(self, session_id: str) -> str:
    """Stage 2+3+4: codebook seed → extract quotes → tag quotes."""
    from asgiref.sync import sync_to_async
    from merism.memai.agents.codebook_seeder import seed_codebook
    from merism.memai.agents.quote_extractor import extract_quotes
    from merism.memai.agents.quote_tagger import (
        promote_inductive_suggestions,
        tag_quotes_for_session,
    )
    from merism.models import InterviewSession

    async def _run():
        @sync_to_async
        def _get():
            return InterviewSession.objects.select_related("study").filter(id=session_id).first()

        session = await _get()
        if session is None:
            return
        await seed_codebook(session.study)
        quotes = await extract_quotes(session)
        if not quotes:
            return
        await tag_quotes_for_session(quotes, session.study)
        await promote_inductive_suggestions(session.study, min_occurrences=2)

    try:
        _run_async(_run())
    except Exception as exc:
        logger.exception("post_session.stage_extract_tag_failed")
        raise self.retry(exc=exc)
    return session_id


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def stage_index_and_insight(self, session_id: str) -> dict[str, Any]:
    """Stage 5+6: RAG indexing + SessionInsight generation."""
    from asgiref.sync import sync_to_async
    from merism.knowledge.indexer import index_session_quotes
    from merism.memai.agents.session_insight_generator import generate_insight
    from merism.models import InterviewSession, SessionQuote

    async def _run():
        @sync_to_async
        def _get():
            return InterviewSession.objects.select_related("study").filter(id=session_id).first()

        @sync_to_async
        def _quotes(s):
            return list(SessionQuote.objects.filter(session=s))

        session = await _get()
        if session is None:
            return {"indexed": 0, "insight_created": 0}
        quotes = await _quotes(session)
        if not quotes:
            return {"indexed": 0, "insight_created": 0}
        indexed = await index_session_quotes(session, quotes)
        insight = await generate_insight(session, quotes)
        return {"indexed": indexed, "insight_created": 1 if insight else 0}

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.exception("post_session.stage_insight_failed")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def process_completed_session(self, session_id: str | UUID) -> dict[str, Any]:
    """Entry point triggered by the InterviewSession post_save signal.

    Kicks off a Celery chain of stage tasks. Keeping a single entry point
    preserves the signal contract while giving each stage independent
    retry / observability.
    """
    try:
        chain(
            stage_polish_transcript.si(str(session_id)),
            stage_extract_and_tag.s(),
            stage_index_and_insight.s(),
        ).apply_async()
        return {"chained": True, "session_id": str(session_id)}
    except Exception as exc:
        logger.exception(
            "post_session.chain_enqueue_failed",
            extra={"session_id": str(session_id)},
        )
        raise self.retry(exc=exc)


# Legacy monolithic path — kept for one-shot admin actions that want a
# synchronous result (e.g. replay endpoint). Hits the same domain code.
@shared_task(bind=True)
def process_completed_session_inline(self, session_id: str | UUID) -> dict[str, int]:
    return _run_async(process_session_transcripts(session_id))


@shared_task
def abandon_stuck_sessions() -> dict[str, int]:
    """Periodic: move in_progress > 2h sessions to COMPLETED with max_duration reason.

    Scheduled via ``CELERY_BEAT_SCHEDULE`` in :mod:`merism.settings.base`.
    Called on a 10-minute cadence; idempotent — runs a fresh SQL filter
    each time so the same stuck session only transitions once.
    """
    from merism.conductor.closure import abandon_stuck_sessions as _run
    count = _run(hours=2)
    return {"abandoned": count}

