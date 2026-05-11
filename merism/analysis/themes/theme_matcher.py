"""Theme matcher — assign a new quote to an existing theme.

Given a new SessionQuote that arrived post-hoc (after the initial
clustering run), decide whether it belongs to an already-known Theme
or should wait for the next re-clustering pass.

Strategy: cosine similarity between the quote's embedding and each
Theme's ``centroid_embedding``. If max sim >= threshold, assign.
Otherwise leave unmatched (the full re-clusterer will pick it up).
"""

from __future__ import annotations

import logging
from uuid import UUID

from asgiref.sync import sync_to_async

from merism.analysis.themes.clusterer import cosine_similarity
from merism.models import SessionQuote, Theme

logger = logging.getLogger(__name__)


MATCH_THRESHOLD = 0.72  # cosine similarity — tuned for text-embedding-3-small


async def match_quote_to_theme(
    quote: SessionQuote,
    quote_embedding: list[float],
    *,
    threshold: float = MATCH_THRESHOLD,
) -> Theme | None:
    """Find the best-matching Theme for a new quote. Returns None if
    no theme crosses the threshold.

    On match, mutates the Theme in-place:
    - Appends the quote_id / session_id to the lists
    - Bumps counters
    - Does NOT recompute the centroid (deferred to full re-clustering)
    """
    themes = await _active_themes_for_study(quote.study_id)
    if not themes:
        return None

    best_theme: Theme | None = None
    best_sim = -1.0

    for theme in themes:
        centroid = theme.centroid_embedding
        if centroid is None:
            continue
        sim = cosine_similarity(quote_embedding, list(centroid))
        if sim > best_sim:
            best_sim = sim
            best_theme = theme

    if best_theme is None or best_sim < threshold:
        logger.debug(
            "themes.matcher.no_match",
            extra={"quote_id": str(quote.id), "best_sim": best_sim},
        )
        return None

    await _assign_quote(best_theme, quote)
    logger.info(
        "themes.matcher.matched",
        extra={
            "theme_id": str(best_theme.id),
            "quote_id": str(quote.id),
            "sim": best_sim,
        },
    )
    return best_theme


@sync_to_async
def _active_themes_for_study(study_id: str | UUID) -> list[Theme]:
    return list(
        Theme.objects.filter(
            study_id=study_id, status__in=[Theme.Status.DRAFT, Theme.Status.CONFIRMED]
        )
    )


@sync_to_async
def _assign_quote(theme: Theme, quote: SessionQuote) -> None:
    quote_ids = list(theme.representative_quote_ids or [])
    session_ids = list(theme.session_ids or [])
    sid = str(quote.session_id)
    if sid not in session_ids:
        session_ids.append(sid)
    theme.session_ids = session_ids
    theme.session_count = len(session_ids)
    theme.quote_count = (theme.quote_count or 0) + 1
    # Update sentiment mix
    tags = quote.tags or {}
    sent = tags.get("sentiment")
    if sent in {"positive", "negative", "neutral", "mixed"}:
        mix = dict(theme.sentiment_mix or {})
        mix[sent] = mix.get(sent, 0) + 1
        theme.sentiment_mix = mix
    theme.save(
        update_fields=[
            "session_ids",
            "session_count",
            "quote_count",
            "sentiment_mix",
            "updated_at",
        ]
    )
