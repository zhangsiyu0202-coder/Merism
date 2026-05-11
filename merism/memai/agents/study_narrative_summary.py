"""Study narrative summary — LangGraph 3-node agent.

Given a study's aggregate analytics + top quotes + session insights,
produces a compact narrative the AnalysisTab's ExecutiveSummary block
renders.

Graph (no fallback):

    outline → draft → polish

Nodes:
- ``outline`` — pick the 2-3 most striking signals from the aggregate
  (cross-cutting themes, extreme numbers, repeated quotes)
- ``draft`` — write the 3-5 sentence narrative based on the outline
- ``polish`` — tighten the prose, ensure no hedging, produce eyebrow+byline
"""

from __future__ import annotations

import json
import logging
from typing import Any, TypedDict
from uuid import uuid4

from asgiref.sync import sync_to_async
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, ConfigDict, Field

from merism.memai.graph import call_llm_json
from merism.models import SessionInsight, SessionQuote, Study
from merism.reports.analysis_service import compute_study_aggregate

logger = logging.getLogger(__name__)


# ── Schemas ────────────────────────────────────────────────


class NarrativeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=40, max_length=1200)
    eyebrow: str = Field(default="", max_length=80)
    byline: str = Field(default="", max_length=120)


# ── State ──────────────────────────────────────────────────


class NarrativeState(TypedDict, total=False):
    # Inputs
    study_id: str
    team: Any
    trace_id: Any
    aggregate: dict[str, Any]
    top_quotes: list[dict[str, Any]]
    session_summaries: list[dict[str, Any]]

    # Intermediate
    outline_bullets: list[str]
    draft_summary: str

    # Outputs
    summary: str
    eyebrow: str
    byline: str


# ── Nodes ──────────────────────────────────────────────────


OUTLINE_PROMPT = """You are the lead researcher drafting a study report.

Look at this study's aggregate analytics + session data. Pick 2-3 SPECIFIC signals a stakeholder would care about most:
- A recurring theme with notable quote support
- An actionable pattern (multiple sessions pointing at the same problem)
- A surprising contrast or strong sentiment cluster

Output JSON only: {"bullets": ["...", "..."]}
Each bullet: one concrete observation with numbers/quote fragments when relevant. No fluff."""


async def outline_node(state: NarrativeState) -> dict[str, Any]:
    payload = {
        "kpi": state["aggregate"]["kpi"],
        "top_themes": state["aggregate"]["top_themes"][:6],
        "top_tasks": state["aggregate"]["top_tasks"][:6],
        "quote_examples": state["top_quotes"][:6],
        "session_summaries": state["session_summaries"][:4],
    }
    result = await call_llm_json(
        team=state["team"],
        trace_id=state["trace_id"],
        messages=[
            {"role": "system", "content": OUTLINE_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        temperature=0.3,
    )
    bullets = result.get("bullets", [])[:4]
    logger.info(
        "study_narrative.outline: study=%s bullets=%d",
        state["study_id"], len(bullets),
    )
    return {"outline_bullets": bullets}


DRAFT_PROMPT = """You write a 3-5 sentence narrative summary of a research study for the Analysis dashboard.

Input: outline bullets (the 2-3 most important findings) + the raw aggregate.

Rules:
- Synthesise — never list session-by-session.
- Speak directly. No "The research found that…". No "Overall…".
- Cite specific numbers when meaningful ("7 of 12 mentioned X").
- Never invent quotes or numbers.
- Plain prose, no bullets, no markdown.

Output JSON only: {"draft": "..."}"""


async def draft_node(state: NarrativeState) -> dict[str, Any]:
    payload = {
        "outline": state.get("outline_bullets", []),
        "kpi": state["aggregate"]["kpi"],
        "research_goal": state["aggregate"].get("research_goal", ""),
        "top_themes": state["aggregate"]["top_themes"][:4],
    }
    result = await call_llm_json(
        team=state["team"],
        trace_id=state["trace_id"],
        messages=[
            {"role": "system", "content": DRAFT_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        temperature=0.4,
    )
    return {"draft_summary": result.get("draft", "").strip()}


POLISH_PROMPT = """You tighten narrative prose for a research report.

Input: a draft summary + the aggregate's session count.

Tasks:
1. Remove hedging ("seems to", "might suggest", "somewhat") — be direct.
2. Cut filler ("overall", "in general", "it is worth noting").
3. Produce an all-caps "eyebrow" one-liner, like "EXECUTIVE SUMMARY · 12 INTERVIEWS".
4. Produce a "byline" like "Generated from 12 interviews".

Keep the final summary under 5 sentences. If the draft is already tight, the final summary can equal the draft.

Output JSON only: {"summary": "...", "eyebrow": "...", "byline": "..."}"""


async def polish_node(state: NarrativeState) -> dict[str, Any]:
    session_count = state["aggregate"]["kpi"].get("session_completed", 0)
    payload = {
        "draft": state.get("draft_summary", ""),
        "session_count": session_count,
    }
    result = await call_llm_json(
        team=state["team"],
        trace_id=state["trace_id"],
        messages=[
            {"role": "system", "content": POLISH_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        temperature=0.2,
    )
    # Fall back to draft if polish returned empty
    summary = result.get("summary") or state.get("draft_summary") or ""
    eyebrow = (
        result.get("eyebrow")
        or f"EXECUTIVE SUMMARY · {session_count} INTERVIEWS"
    )
    byline = result.get("byline") or f"Generated from {session_count} interviews"
    return {"summary": summary.strip(), "eyebrow": eyebrow, "byline": byline}


# ── Graph ──────────────────────────────────────────────────


def _build_graph():
    g = StateGraph(NarrativeState)
    g.add_node("outline", outline_node)
    g.add_node("draft", draft_node)
    g.add_node("polish", polish_node)
    g.set_entry_point("outline")
    g.add_edge("outline", "draft")
    g.add_edge("draft", "polish")
    g.add_edge("polish", END)
    return g.compile()


_GRAPH = None


def _get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = _build_graph()
    return _GRAPH


# ── Public API ─────────────────────────────────────────────


async def summarize_study(study: Study) -> dict[str, Any] | None:
    """Generate a narrative summary for the AnalysisTab.

    Returns ``{summary, eyebrow, byline}`` or ``None`` on failure.
    No LLM fallback — graph errors propagate to None.
    """
    aggregate = await sync_to_async(compute_study_aggregate)(study)
    if aggregate["kpi"]["quote_count"] == 0:
        return None

    top_quotes = await _atop_quotes(study, limit=8)
    insight_summaries = await _ainsight_summaries(study, limit=6)

    initial_state: NarrativeState = {
        "study_id": str(study.id),
        "team": study.team,
        "trace_id": uuid4(),
        "aggregate": {
            **aggregate,
            "research_goal": study.research_goal or "",
        },
        "top_quotes": [
            {"text": q.text, "tags": q.tags or {}, "importance": q.importance}
            for q in top_quotes
        ],
        "session_summaries": insight_summaries,
    }

    try:
        graph = _get_graph()
        final_state = await graph.ainvoke(initial_state)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "study_narrative.graph_failed: study=%s error=%s",
            str(study.id), str(exc),
        )
        return None

    summary = final_state.get("summary", "")
    if not summary:
        return None

    return {
        "summary": summary,
        "eyebrow": final_state.get("eyebrow", ""),
        "byline": final_state.get("byline", ""),
    }


# ── DB helpers ──────────────────────────────────────────────


@sync_to_async
def _atop_quotes(study: Study, *, limit: int = 8) -> list[SessionQuote]:
    return list(
        SessionQuote.objects.filter(study=study)
        .order_by("-importance", "ts_start_ms")[:limit]
    )


@sync_to_async
def _ainsight_summaries(study: Study, *, limit: int = 6) -> list[dict[str, Any]]:
    rows = SessionInsight.objects.filter(session__study=study).order_by("-created_at")[:limit]
    return [
        {"session_id": str(r.session_id), "summary": r.summary, "tags": r.tags or {}}
        for r in rows
    ]
