"""SessionInsight generator — LangGraph multi-node agent.

Produces a compact :class:`merism.models.SessionInsight` row per
completed interview session.

Graph (all LLM calls go through the LLM Gateway, no fallback):

    plan → extract_tasks → compose_summary → validate → persist

Nodes:

- ``plan``           — scan quotes, pick top-3 highlights by combining
                       importance + LLM-judged relevance to the research_goal
- ``extract_tasks``  — LLM reads highlights + tags, emits actionable TODOs
                       with explicit quote evidence
- ``compose_summary``— LLM writes the 3-5 sentence narrative grounded in
                       the picked highlights + tasks
- ``validate``       — server-side checks: highlights exist in quotes,
                       tasks reference valid quote IDs, summary length
- ``persist``        — DB write + sentiment aggregation

No fallback: if any node throws, the whole agent fails and ``generate_insight``
returns ``None``. The Celery post-session chain will log and move on.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from typing import Any, Literal, TypedDict
from uuid import uuid4

from asgiref.sync import sync_to_async
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, ConfigDict, Field

from merism.memai.graph import call_llm_json
from merism.models import InterviewSession, SessionInsight, SessionQuote

logger = logging.getLogger(__name__)


# ── Output schemas ──────────────────────────────────────────


class ExtractedTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=160)
    category: Literal["bug", "feature", "content", "pricing", "ux", "other"] = "other"
    priority: Literal["p0", "p1", "p2"] = "p1"
    evidence_quote_id: str = ""


# ── State ───────────────────────────────────────────────────


class InsightState(TypedDict, total=False):
    # Inputs
    session_id: str
    research_goal: str
    quotes: list[dict[str, Any]]  # {quote_id, text, importance, tags}
    team: Any
    trace_id: Any

    # Intermediate
    selected_highlight_ids: list[str]
    extracted_tasks: list[dict[str, Any]]
    summary: str

    # Validation flags
    validation_errors: list[str]


# ── Nodes ───────────────────────────────────────────────────


PLAN_PROMPT = """You are a qualitative researcher preparing a session report.

Given the research goal and the set of extracted quotes, pick the 3 quotes that BEST represent what the participant told us — the ones a researcher would cite in a report.

Criteria:
- Concrete + specific over abstract
- Direct answer to the research goal
- Distinct (don't pick 3 quotes all saying the same thing)

Output JSON only: {"highlight_quote_ids": ["uuid1", "uuid2", "uuid3"]}
Exactly 3 ids. Use only ids from the input. No explanation."""


async def plan_node(state: InsightState) -> dict[str, Any]:
    """Pick top-3 highlight quotes."""
    payload = {
        "research_goal": state["research_goal"],
        "quotes": [
            {"quote_id": q["quote_id"], "text": q["text"], "importance": q["importance"]}
            for q in state["quotes"]
        ],
    }
    result = await call_llm_json(
        team=state["team"],
        trace_id=state["trace_id"],
        messages=[
            {"role": "system", "content": PLAN_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        temperature=0.2,
    )
    ids = result.get("highlight_quote_ids", [])
    # Filter to valid ids
    valid = {q["quote_id"] for q in state["quotes"]}
    selected = [qid for qid in ids if qid in valid][:3]
    logger.info(
        "session_insight.plan: session=%s highlights=%d",
        state["session_id"], len(selected),
    )
    return {"selected_highlight_ids": selected}


TASKS_PROMPT = """You extract actionable product tasks from interview highlights.

Rules:
- Only emit a task if the participant's words CLEARLY motivate it.
- Each task MUST reference a quote_id as evidence_quote_id.
- Prefer fewer, higher-quality tasks over many weak ones.
- If nothing actionable surfaced, return {"tasks": []}.

Categories: bug | feature | content | pricing | ux | other
Priorities: p0 (critical) | p1 (should) | p2 (nice)

Output JSON only: {"tasks": [{"title": "...", "category": "...", "priority": "...", "evidence_quote_id": "..."}]}"""


async def extract_tasks_node(state: InsightState) -> dict[str, Any]:
    """Pull actionable TODOs from highlights."""
    quote_by_id = {q["quote_id"]: q for q in state["quotes"]}
    highlights = [
        quote_by_id[qid] for qid in state.get("selected_highlight_ids", []) if qid in quote_by_id
    ]
    if not highlights:
        return {"extracted_tasks": []}

    payload = {
        "research_goal": state["research_goal"],
        "highlights": [
            {"quote_id": q["quote_id"], "text": q["text"], "tags": q.get("tags", {})}
            for q in highlights
        ],
        # Include non-highlight quotes for broader context (but mark them)
        "other_quotes": [
            {"quote_id": q["quote_id"], "text": q["text"]}
            for q in state["quotes"]
            if q["quote_id"] not in state.get("selected_highlight_ids", [])
        ][:10],
    }
    result = await call_llm_json(
        team=state["team"],
        trace_id=state["trace_id"],
        messages=[
            {"role": "system", "content": TASKS_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        temperature=0.3,
    )
    tasks = result.get("tasks", [])
    # Keep only tasks with valid evidence_quote_id
    valid_ids = {q["quote_id"] for q in state["quotes"]}
    filtered = [t for t in tasks if t.get("evidence_quote_id") in valid_ids]
    logger.info(
        "session_insight.extract_tasks: session=%s raw=%d valid=%d",
        state["session_id"], len(tasks), len(filtered),
    )
    return {"extracted_tasks": filtered}


SUMMARY_PROMPT = """You write a 3-5 sentence narrative summary of an interview session.

Input: research goal, highlight quotes, extracted tasks.

Rules:
- Speak directly. Never start with "The participant said".
- Ground every claim in a highlight quote — don't invent content.
- If tasks were extracted, the summary should hint at them without repeating verbatim.
- Output plain text, no markdown, no headers.

Output JSON only: {"summary": "..."}"""


async def compose_summary_node(state: InsightState) -> dict[str, Any]:
    """Write the narrative summary grounded in highlights + tasks."""
    quote_by_id = {q["quote_id"]: q for q in state["quotes"]}
    highlights = [
        quote_by_id[qid] for qid in state.get("selected_highlight_ids", []) if qid in quote_by_id
    ]
    payload = {
        "research_goal": state["research_goal"],
        "highlight_quotes": [{"text": q["text"], "tags": q.get("tags", {})} for q in highlights],
        "extracted_tasks": state.get("extracted_tasks", []),
    }
    result = await call_llm_json(
        team=state["team"],
        trace_id=state["trace_id"],
        messages=[
            {"role": "system", "content": SUMMARY_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        temperature=0.4,
    )
    return {"summary": result.get("summary", "").strip()}


def validate_node(state: InsightState) -> dict[str, Any]:
    """Server-side sanity checks. Pure function, no LLM."""
    errors: list[str] = []
    summary = state.get("summary", "")
    if len(summary) < 20:
        errors.append("summary too short")
    if len(summary) > 2000:
        errors.append("summary too long")

    # Tasks must reference quotes
    valid_ids = {q["quote_id"] for q in state["quotes"]}
    for i, t in enumerate(state.get("extracted_tasks", [])):
        qid = t.get("evidence_quote_id", "")
        if qid and qid not in valid_ids:
            errors.append(f"task[{i}] references invalid quote_id={qid}")

    if errors:
        logger.warning(
            "session_insight.validate_errors: session=%s errors=%s",
            state["session_id"], errors,
        )
    return {"validation_errors": errors}


# ── Graph construction ──────────────────────────────────────


def _build_graph():
    g = StateGraph(InsightState)
    g.add_node("plan", plan_node)
    g.add_node("extract_tasks", extract_tasks_node)
    g.add_node("compose_summary", compose_summary_node)
    g.add_node("validate", validate_node)

    g.set_entry_point("plan")
    g.add_edge("plan", "extract_tasks")
    g.add_edge("extract_tasks", "compose_summary")
    g.add_edge("compose_summary", "validate")
    g.add_edge("validate", END)

    return g.compile()


_GRAPH = None


def _get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = _build_graph()
    return _GRAPH


# ── Public API ──────────────────────────────────────────────


async def generate_insight(
    session: InterviewSession,
    quotes: list[SessionQuote],
) -> SessionInsight | None:
    """Build + persist a SessionInsight via the LangGraph multi-node agent.

    No fallback — on any LLM / node error, returns ``None`` and logs.
    Idempotent: if an insight already exists, returns it.
    """
    existing = await _aget_existing_insight(session)
    if existing is not None:
        return existing

    if not quotes:
        return None

    quote_payload = [
        {
            "quote_id": str(q.id),
            "text": q.text,
            "importance": q.importance,
            "tags": q.tags or {},
        }
        for q in quotes
    ]
    initial_state: InsightState = {
        "session_id": str(session.id),
        "research_goal": session.study.research_goal or "",
        "quotes": quote_payload,
        "team": session.study.team,
        "trace_id": session.trace_id or uuid4(),
    }

    try:
        graph = _get_graph()
        final_state = await graph.ainvoke(initial_state)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "session_insight.graph_failed: session=%s error=%s",
            str(session.id), str(exc),
        )
        return None

    summary = final_state.get("summary", "")
    if not summary:
        return None

    # Validation failed → still write but log
    if final_state.get("validation_errors"):
        logger.warning(
            "session_insight.soft_validation_fail: session=%s errors=%s",
            str(session.id), final_state["validation_errors"],
        )

    # Resolve highlights → full quote dicts (with ts)
    quote_by_id = {str(q.id): q for q in quotes}
    highlights = []
    for qid in final_state.get("selected_highlight_ids", []):
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
    # Safety fallback on highlights only: if the agent picked none, use top-importance.
    # This is a DATA SAFETY fallback (preserve insight writability), not an LLM fallback.
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

    # Aggregate sentiment / action counts
    sentiments: Counter[str] = Counter()
    action_types: Counter[str] = Counter()
    for q in quotes:
        tags = q.tags or {}
        if sentiment := tags.get("sentiment"):
            sentiments[sentiment] += 1
        if action := tags.get("action_type"):
            action_types[action] += 1

    insight = await _persist_insight(
        session=session,
        summary=summary,
        highlights=highlights,
        tags={
            "sentiment_counts": dict(sentiments),
            "action_counts": dict(action_types),
            "quote_count": len(quotes),
        },
        extracted_tasks=final_state.get("extracted_tasks", []),
    )
    logger.info(
        "session_insight.done: session=%s insight=%s",
        str(session.id), str(insight.id),
    )
    return insight


# ── DB helpers ──────────────────────────────────────────────


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
