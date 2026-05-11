"""SessionInsight generator — the per-session narrative.

After quotes are extracted + tagged, this agent produces a compact
:class:`merism.models.SessionInsight` row containing:

- ``summary`` — 3-5 sentences capturing what the participant was
  really saying.
- ``highlights`` — top 3 quotes (by importance) with their verbatim
  text + timestamp.
- ``tags`` — aggregate counts of sentiment + action_type across the
  session's quotes.
- ``extracted_tasks`` — actionable TODOs the participant implied
  ("add dark mode", "fix the pricing page").

This is the signal Inbox / Repository / Decisions surfaces consume.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from typing import Literal

from asgiref.sync import sync_to_async
from pydantic import BaseModel, ConfigDict, Field

from merism.memai.llm import LLMUnavailableError, default_model, get_llm
from merism.models import InterviewSession, SessionInsight, SessionQuote

logger = logging.getLogger(__name__)


# ── Output schema ─────────────────────────────────────────────

class ExtractedTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=160)
    category: Literal["bug", "feature", "content", "pricing", "ux", "other"] = "other"
    priority: Literal["P0", "P1", "P2"] = "P1"
    evidence_quote_id: str = Field(default="", description="Matches a quote id from input")


class InsightOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=10, max_length=1500)
    highlight_quote_ids: list[str] = Field(default_factory=list, max_length=5)
    extracted_tasks: list[ExtractedTask] = Field(default_factory=list, max_length=6)


SYSTEM_PROMPT = """\
You synthesise one participant interview into a compact insight.

Input: a JSON object with
  - ``research_goal``: the study's north-star question
  - ``quotes``: a list of {quote_id, text, importance, tags} already
    extracted from the session

Output JSON:
  {
    "summary": "...",                   // 3-5 sentences
    "highlight_quote_ids": ["...", ...],  // at most 3 quote_ids
    "extracted_tasks": [ {...}, ... ]    // 0-6 actionable TODOs
  }

Rules:
- ``summary`` answers: what did THIS participant actually tell us?
  Focus on their specific story, not generic observations. No preamble
  ("The participant said that..."). Speak directly.
- ``highlight_quote_ids`` are pulled from the input; do not invent ids.
  Pick the 3 quotes that together best represent the participant.
- ``extracted_tasks`` are TODOs the participant implicitly or
  explicitly suggested — product tickets worth considering. Each task
  must cite an ``evidence_quote_id`` from the input. Only include a
  task if the participant's words clearly motivate it.
- Skip tasks if the session didn't surface any — don't pad.
"""


async def generate_insight(
    session: InterviewSession,
    quotes: list[SessionQuote],
) -> SessionInsight | None:
    """Build + persist a SessionInsight for a completed session.

    Returns the SessionInsight row or ``None`` on failure (no row is
    written). Idempotent: if an insight already exists, returns it.
    """
    existing = await _aget_existing_insight(session)
    if existing is not None:
        return existing

    if not quotes:
        return None

    # Prepare quote payload for the LLM.
    payload = {
        "research_goal": session.study.research_goal or "",
        "quotes": [
            {
                "quote_id": str(q.id),
                "text": q.text,
                "importance": q.importance,
                "tags": q.tags or {},
            }
            for q in quotes
        ],
    }

    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        gw_client = None
        try:
            from merism.llm_gateway.client import get_client

            gw_client = await get_client("chat", team=session.study.team, trace_id=session.trace_id)
        except Exception:
            pass

        if gw_client:
            response = await gw_client.complete(
                messages=messages, response_format={"type": "json_object"}, temperature=0.3,
            )
            raw = response.choices[0].message.content or "{}"
        else:
            client = get_llm(async_=True)
            completion = await client.chat.completions.create(
                model=default_model(),
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            raw = completion.choices[0].message.content or "{}"
        parsed = InsightOutput.model_validate_json(raw)
    except (LLMUnavailableError, Exception) as exc:  # noqa: BLE001
        logger.warning(
            "session_insight.llm_failed",
            extra={"error": str(exc), "session_id": str(session.id)},
        )
        return None

    # Resolve highlight_quote_ids to the actual quote rows.
    quote_by_id = {str(q.id): q for q in quotes}
    highlights = []
    for qid in parsed.highlight_quote_ids[:3]:
        q = quote_by_id.get(qid)
        if q is None:
            continue
        highlights.append(
            {
                "quote_id": str(q.id),
                "text": q.text,
                "ts_start_ms": q.ts_start_ms,
                "ts_end_ms": q.ts_end_ms,
                "importance": q.importance,
            }
        )
    # Fallback: if LLM didn't provide highlights, take top-importance quotes.
    if not highlights:
        ranked = sorted(quotes, key=lambda q: -q.importance)[:3]
        highlights = [
            {
                "quote_id": str(q.id),
                "text": q.text,
                "ts_start_ms": q.ts_start_ms,
                "ts_end_ms": q.ts_end_ms,
                "importance": q.importance,
            }
            for q in ranked
        ]

    # Aggregate sentiment / action_type counts across the session.
    sentiments = Counter()
    action_types = Counter()
    for q in quotes:
        tags = q.tags or {}
        if sentiment := tags.get("sentiment"):
            sentiments[sentiment] += 1
        if action := tags.get("action_type"):
            action_types[action] += 1

    tasks = [
        {
            "title": t.title,
            "category": t.category,
            "priority": t.priority,
            "evidence_quote_id": t.evidence_quote_id,
        }
        for t in parsed.extracted_tasks
        if t.evidence_quote_id in quote_by_id or not t.evidence_quote_id
    ]

    insight = await _persist_insight(
        session=session,
        summary=parsed.summary,
        highlights=highlights,
        tags={
            "sentiment_counts": dict(sentiments),
            "action_counts": dict(action_types),
            "quote_count": len(quotes),
        },
        extracted_tasks=tasks,
    )
    logger.info(
        "session_insight.done",
        extra={"session_id": str(session.id), "insight_id": str(insight.id)},
    )
    return insight


# ── DB helpers ──

@sync_to_async
def _aget_existing_insight(session: InterviewSession) -> SessionInsight | None:
    return SessionInsight.objects.filter(session=session).first()


@sync_to_async
def _persist_insight(
    *,
    session: InterviewSession,
    summary: str,
    highlights: list[dict],
    tags: dict,
    extracted_tasks: list[dict],
) -> SessionInsight:
    insight, _created = SessionInsight.objects.update_or_create(
        session=session,
        defaults={
            "team": session.team,
            "summary": summary,
            "highlights": highlights,
            "tags": tags,
            "extracted_tasks": extracted_tasks,
            "trace_id": session.trace_id,
        },
    )
    return insight
