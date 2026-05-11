"""Cross-session analysis orchestrator.

Called from ``conductor/post_session.py`` after each session completes.
Rebuilds themes + coverage snapshot for the whole study.

Strategy: full rebuild is simple + correct. Incremental matching (new
quotes to existing themes) is an optimization for later.
"""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from asgiref.sync import sync_to_async
from celery import shared_task

from merism.analysis.themes.clusterer import cluster_quote_embeddings
from merism.analysis.themes.embedder import fetch_study_quote_embeddings
from merism.models import SessionQuote, Study, Theme

logger = logging.getLogger(__name__)

# Minimum quotes across the study before we try to cluster
MIN_QUOTES_FOR_CLUSTERING = 8


async def rebuild_study_analysis(study_id: str | UUID) -> dict[str, int]:
    """Full rebuild: themes + coverage snapshot.

    Returns counters: {themes_created, coverage_gaps, sessions}
    """
    counters = {"themes_created": 0, "coverage_gaps": 0, "sessions": 0}

    study = await _aget_study(study_id)
    if study is None:
        return counters

    # ── Themes ──
    samples = await fetch_study_quote_embeddings(study.id)
    counters["sessions"] = len({s["session_id"] for s in samples})

    if len(samples) >= MIN_QUOTES_FOR_CLUSTERING:
        result = cluster_quote_embeddings(samples, min_cluster_size=3)

        # Archive old auto-generated themes before creating new ones
        await _archive_draft_themes(study.id)

        # For each cluster, summarize and persist
        from merism.analysis.themes.theme_summarizer import summarize_cluster

        # Build quote lookup
        quotes_by_id = await _fetch_quotes_by_ids(
            [s["quote_id"] for s in samples]
        )
        session_by_quote = {s["quote_id"]: s["session_id"] for s in samples}

        for cluster_id, quote_ids in result.clusters.items():
            if not quote_ids:
                continue
            # Representative = top 5 closest to centroid (already sorted)
            rep_ids = quote_ids[:5]
            rep_quotes = [quotes_by_id[qid] for qid in rep_ids if qid in quotes_by_id]
            all_session_ids = [session_by_quote.get(qid, "") for qid in quote_ids]
            centroid = result.centroids.get(cluster_id)
            theme = await summarize_cluster(
                study,
                rep_quotes,
                all_quote_ids=quote_ids,
                all_session_ids=[s for s in all_session_ids if s],
                centroid=centroid,
                trace_id=uuid4(),
            )
            if theme:
                counters["themes_created"] += 1
    else:
        logger.info(
            "analysis.pipeline.not_enough_quotes: study=%s have=%d need=%d",
            str(study.id), len(samples), MIN_QUOTES_FOR_CLUSTERING,
        )

    # ── Coverage ──
    from merism.analysis.coverage.goal_coverage import compute_coverage_snapshot

    try:
        snap = await compute_coverage_snapshot(study)
        if snap:
            counters["coverage_gaps"] = len(snap.gaps or [])
    except Exception:
        logger.exception("analysis.pipeline.coverage_failed", extra={"study_id": str(study.id)})

    logger.info(
        "analysis.pipeline.done: study=%s themes=%d gaps=%d sessions=%d",
        str(study.id), counters["themes_created"], counters["coverage_gaps"],
        counters["sessions"],
    )
    return counters


# ── Celery task wrapper ──

@shared_task(name="merism.analysis.pipeline.rebuild_study_analysis_task")
def rebuild_study_analysis_task(study_id: str) -> dict[str, int]:
    """Sync Celery wrapper. Uses asgiref to call the async impl."""
    from asgiref.sync import async_to_sync

    return async_to_sync(rebuild_study_analysis)(study_id)


# ── DB helpers ──


@sync_to_async
def _aget_study(study_id: str | UUID) -> Study | None:
    try:
        return Study.objects.select_related("team").get(id=study_id)
    except Study.DoesNotExist:
        return None


@sync_to_async
def _archive_draft_themes(study_id: str | UUID) -> int:
    # Archive instead of delete — preserves history
    return Theme.objects.filter(
        study_id=study_id, status=Theme.Status.DRAFT
    ).update(status=Theme.Status.ARCHIVED)


@sync_to_async
def _fetch_quotes_by_ids(quote_ids: list[str]) -> dict[str, SessionQuote]:
    rows = SessionQuote.objects.filter(id__in=quote_ids)
    return {str(q.id): q for q in rows}
