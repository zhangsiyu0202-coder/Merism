"""Study narrative summary.

Given a study's aggregate analytics + top quotes + session insights,
produces a compact 3-5 sentence narrative the AnalysisTab's
ExecutiveSummary block renders. Cached on ``Study.metadata`` (not yet
a real field — stored on a soft JSONField-style fallback) so unchanged
studies don't re-hit DeepSeek.
"""

from __future__ import annotations

import json
import logging
from uuid import uuid4
from typing import Any

from asgiref.sync import sync_to_async
from pydantic import BaseModel, ConfigDict, Field

from merism.memai.llm import LLMUnavailableError, default_model, get_llm
from merism.models import SessionInsight, SessionQuote, Study
from merism.reports.analysis_service import compute_study_aggregate

logger = logging.getLogger(__name__)


class NarrativeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=40, max_length=1200)
    eyebrow: str = Field(default="", max_length=80)
    byline: str = Field(default="", max_length=120)


SYSTEM_PROMPT = """\
You are the lead researcher on a qualitative study. Given an aggregate
summary of the study, produce a compact narrative the research team
will read at the top of their analysis dashboard.

Rules:
- ``summary`` is 3-5 sentences. It should answer: what did participants
  actually tell us? Cite specific numbers when they're meaningful
  (e.g. "7 of 12 mentioned X"). Do NOT summarise individual sessions
  one by one. Synthesise across them.
- ``eyebrow`` is one short line ALL CAPS tag ("EXECUTIVE SUMMARY · N
  INTERVIEWS").
- ``byline`` credits the sample size + date ("Generated from 12
  interviews · updated today").
- Never invent quotes or numbers. Use only what appears in the input.
- Speak directly — no preamble like "The research found that…".
- If the input is sparse (<3 quotes), return a shorter summary
  acknowledging early-stage data.
"""


async def summarize_study(study: Study) -> dict[str, Any] | None:
    """Generate a narrative summary for the AnalysisTab."""
    aggregate = await sync_to_async(compute_study_aggregate)(study)
    if aggregate["kpi"]["quote_count"] == 0:
        return None

    # Include up to 8 highest-importance quotes for flavour.
    top_quotes = await _atop_quotes(study, limit=8)
    insight_summaries = await _ainsight_summaries(study, limit=6)

    payload = {
        "research_goal": study.research_goal or "",
        "research_objectives": study.research_objectives or [],
        "kpi": aggregate["kpi"],
        "top_themes": aggregate["top_themes"][:6],
        "top_tasks": aggregate["top_tasks"][:6],
        "quote_examples": [
            {"text": q.text, "tags": q.tags or {}, "importance": q.importance}
            for q in top_quotes
        ],
        "session_summaries": insight_summaries,
    }

    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        gw_client = None
        try:
            from merism.llm_gateway.client import get_client

            gw_client = await get_client("chat", team=study.team, trace_id=uuid4())
        except Exception:
            pass

        if gw_client:
            response = await gw_client.complete(
                messages=messages, response_format={"type": "json_object"}, temperature=0.35,
            )
            raw = response.choices[0].message.content or "{}"
        else:
            client = get_llm(async_=True)
            completion = await client.chat.completions.create(
                model=default_model(),
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.35,
            )
            raw = completion.choices[0].message.content or "{}"
        parsed = NarrativeOutput.model_validate_json(raw)
    except (LLMUnavailableError, Exception) as exc:  # noqa: BLE001
        logger.warning(
            "study_narrative.llm_failed",
            extra={"error": str(exc), "study_id": str(study.id)},
        )
        return None

    return {
        "summary": parsed.summary,
        "eyebrow": parsed.eyebrow
        or f"EXECUTIVE SUMMARY · {aggregate['kpi']['session_completed']} INTERVIEWS",
        "byline": parsed.byline
        or f"Generated from {aggregate['kpi']['session_completed']} interviews",
    }


@sync_to_async
def _atop_quotes(study: Study, *, limit: int = 8) -> list[SessionQuote]:
    return list(
        SessionQuote.objects.filter(study=study)
        .order_by("-importance", "ts_start_ms")[:limit]
    )


@sync_to_async
def _ainsight_summaries(study: Study, *, limit: int = 6) -> list[str]:
    return list(
        SessionInsight.objects.filter(session__study=study)
        .order_by("-created_at")
        .values_list("summary", flat=True)[:limit]
    )
