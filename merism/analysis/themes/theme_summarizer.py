"""Theme summarizer — LLM turns each cluster into a named theme.

For each cluster:
1. Pick top-K representative quotes (closest to centroid)
2. Ask LLM to produce {name, description, sentiment_mix}
3. Persist as Theme rows

Uses the LLM Gateway's chat route with JSON output.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from typing import Any
from uuid import UUID, uuid4

from asgiref.sync import sync_to_async
from pydantic import BaseModel, ConfigDict, Field

from merism.models import SessionQuote, Study, Theme

logger = logging.getLogger(__name__)


# ── LLM output schema ───────────────────────────────────────

class ThemeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=500)


# ── Prompts ─────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a qualitative-research analyst. You will be given a cluster of verbatim quotes from different interview participants. All quotes share a semantic theme.

Your task:
1. Write a concise theme name (3-8 words) that captures the shared idea.
2. Write a 1-2 sentence description explaining what connects these quotes.

Style rules:
- Name the pattern, not the data. "Pricing perceived as high" > "People mentioned pricing".
- No hedging ("some users seem to..."). Be direct.
- Don't invent content. Only use what's in the quotes.

Output JSON only: {"name": "...", "description": "..."}"""


USER_PROMPT_TEMPLATE = """Cluster with {count} quotes from {session_count} sessions:

{quotes_text}"""


# ── Public API ──────────────────────────────────────────────


async def summarize_cluster(
    study: Study,
    representative_quotes: list[SessionQuote],
    *,
    all_quote_ids: list[str],
    all_session_ids: list[str],
    centroid: list[float] | None,
    trace_id: UUID | None = None,
) -> Theme | None:
    """Summarize a single cluster into a Theme row.

    ``representative_quotes`` — top 3-5 closest to centroid
    ``all_quote_ids`` — every quote in the cluster
    ``all_session_ids`` — unique session ids contributing to the cluster
    ``centroid`` — mean embedding of the cluster (for future matching)

    Returns the created Theme or None on LLM failure.
    """
    if not representative_quotes:
        return None

    quotes_text = "\n".join(
        f"- ({i+1}) {q.text.strip()}" for i, q in enumerate(representative_quotes)
    )
    user_msg = USER_PROMPT_TEMPLATE.format(
        count=len(all_quote_ids),
        session_count=len(set(all_session_ids)),
        quotes_text=quotes_text,
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    # Try gateway first, fall back to legacy get_llm()
    raw: str | None = None
    try:
        from merism.llm_gateway.client import get_client

        client = await get_client("chat", team=study.team, trace_id=trace_id or uuid4())
        response = await client.complete(
            messages=messages, response_format={"type": "json_object"}, temperature=0.3,
        )
        raw = response.choices[0].message.content or "{}"
    except Exception:
        try:
            from merism.memai.llm import default_model, get_llm

            legacy = get_llm(async_=True)
            completion = await legacy.chat.completions.create(
                model=default_model(),
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            raw = completion.choices[0].message.content or "{}"
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "themes.summarizer.llm_failed",
                extra={"error": str(exc), "study_id": str(study.id)},
            )
            return None

    try:
        parsed = ThemeOutput.model_validate_json(raw)
    except Exception:
        logger.warning("themes.summarizer.parse_failed", extra={"raw": raw[:200]})
        return None

    # Compute sentiment mix from quotes.tags
    sentiment_mix = _compute_sentiment_mix(representative_quotes)

    # Representative = the quotes we showed the LLM (top-K by centroid distance)
    rep_ids = [str(q.id) for q in representative_quotes]

    theme = await sync_to_async(Theme.objects.create)(
        team=study.team,
        study=study,
        name=parsed.name,
        description=parsed.description,
        representative_quote_ids=rep_ids,
        session_ids=list(set(all_session_ids)),
        session_count=len(set(all_session_ids)),
        quote_count=len(all_quote_ids),
        sentiment_mix=sentiment_mix,
        centroid_embedding=centroid,
        status=Theme.Status.DRAFT,
    )
    logger.info(
        "themes.summarizer.created",
        extra={
            "theme_id": str(theme.id),
            "study_id": str(study.id),
            "quote_count": len(all_quote_ids),
            "session_count": len(set(all_session_ids)),
        },
    )
    return theme


def _compute_sentiment_mix(quotes: list[SessionQuote]) -> dict[str, int]:
    """Tally sentiment labels from quote.tags['sentiment']."""
    counter: Counter[str] = Counter()
    for q in quotes:
        tags = q.tags or {}
        sent = tags.get("sentiment")
        if sent in {"positive", "negative", "neutral", "mixed"}:
            counter[sent] += 1
    return dict(counter)
