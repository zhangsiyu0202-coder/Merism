"""Analysis Agent — PRODUCT.md §5.3.

Two entry points:

- :func:`generate_session_insight` — (A) individual-session analysis. One
  LLM call after a session completes, produces ``SessionInsight``
  (summary / highlights / tags / extracted_tasks).
- :func:`answer_custom_report_question` — (B) Custom Report Q&A. One LLM
  call with three tools the agent may call: ``aggregate_tag`` /
  ``filter_sessions`` / ``cite_quote``. Returns a ``CustomReportAnswer``
  with markdown + chart_spec + citations.

Both paths obey the Merism rule that analysis results must be grounded in
actual interview data — the custom_report path uses the callable tools to
prevent hallucinated numbers / quotes.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from merism.memai.llm import default_model, get_llm, reasoner_model
from merism.models import InterviewSession, SessionInsight, Study
from merism.reports.schema import (
    ChartSpec,
    Citation,
    CustomReportAnswer,
)

logger = logging.getLogger(__name__)


# ── (A) Individual session analysis ────────────────────────


class SessionInsightPayload(BaseModel):
    """Shape the LLM must return for session analysis."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(..., min_length=1)
    highlights: list[dict[str, Any]] = Field(default_factory=list)
    tags: dict[str, Any] = Field(default_factory=dict)
    extracted_tasks: list[dict[str, Any]] = Field(default_factory=list)


_SESSION_INSIGHT_PROMPT = """\
You are an analyst summarising one interview session.

Produce a structured insight:
- ``summary``: 3-5 sentences capturing the participant's key perspectives.
- ``highlights``: 3-8 short verbatim passages the researcher should hear,
  each with ``text``, ``ts_start``, ``ts_end``, ``importance`` (0-1).
- ``tags``: a dict of dimension_name → value. Dimensions are YOU deciding
  which facets of the answer matter for THIS ``research_goal`` — do not
  reuse a fixed taxonomy across studies.
- ``extracted_tasks``: action items the researcher might act on, each
  with ``title``, ``category``, ``priority`` (p0/p1/p2),
  ``evidence_quote_id``.
"""

_SUBMIT_INSIGHT_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_session_insight",
        "description": "Return the structured session insight.",
        "parameters": SessionInsightPayload.model_json_schema(),
    },
}


def generate_session_insight(session: InterviewSession) -> SessionInsight:
    """Run the session-insight LLM call and persist the result.

    Called from a Celery task after the interview ends. Uses the DeepSeek
    Reasoner model by default — deeper analysis, higher latency acceptable
    because this runs async.
    """
    study = session.study
    transcript_text = _format_transcript(session.transcript or [])
    messages = [
        {"role": "system", "content": _SESSION_INSIGHT_PROMPT},
        {
            "role": "system",
            "content": (
                "<research_goal>\n"
                f"{study.research_goal.strip()}\n"
                "</research_goal>\n\n"
                "<transcript>\n"
                f"{transcript_text}\n"
                "</transcript>\n"
            ),
        },
        {"role": "user", "content": "Generate the session insight now."},
    ]

    client = get_llm()
    completion = client.chat.completions.create(
        model=reasoner_model(),
        messages=messages,
        tools=[_SUBMIT_INSIGHT_TOOL],
        tool_choice={"type": "function", "function": {"name": "submit_session_insight"}},
    )
    payload = _parse_tool_call(completion, SessionInsightPayload)
    if payload is None:
        raise RuntimeError("SessionInsight LLM produced no tool call")

    insight, _ = SessionInsight.objects.update_or_create(
        session=session,
        defaults={
            "team": session.team,
            "summary": payload.summary,
            "highlights": payload.highlights,
            "tags": payload.tags,
            "extracted_tasks": payload.extracted_tasks,
        },
    )
    return insight


def _format_transcript(transcript: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for i, turn in enumerate(transcript):
        role = turn.get("role", "?")
        text = (turn.get("text") or "").strip()
        if not text:
            continue
        lines.append(f"[{i:03d}] {role}: {text}")
    return "\n".join(lines)


# ── (B) Custom Report Q&A ──────────────────────────────────


_CUSTOM_REPORT_PROMPT = """\
You answer research questions about a team's studies. You MUST ground
every claim in data returned by the provided tools — never invent
numbers, percentages, or quotes. If you lack data to answer honestly,
say so in ``answer_markdown``.

Tools:
- ``aggregate_tag(tag_name)``: returns distribution of one tag across
  sessions in scope.
- ``filter_sessions(criteria)``: returns session_ids matching a filter.
- ``cite_quote(session_id, ts)``: returns the verbatim quote at that
  timestamp (use this for every citation).

When a chart helps, set ``chart`` with the ChartSpec shape
(type bar/line/pie, title, x, y, unit). When it doesn't, leave
``chart: null``.
"""


_AGGREGATE_TAG_TOOL = {
    "type": "function",
    "function": {
        "name": "aggregate_tag",
        "description": "Count distribution of one tag across sessions in scope.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"tag_name": {"type": "string"}},
            "required": ["tag_name"],
        },
    },
}

_FILTER_SESSIONS_TOOL = {
    "type": "function",
    "function": {
        "name": "filter_sessions",
        "description": "Return session_ids matching a filter expression.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"criteria": {"type": "object"}},
            "required": ["criteria"],
        },
    },
}

_CITE_QUOTE_TOOL = {
    "type": "function",
    "function": {
        "name": "cite_quote",
        "description": "Fetch the verbatim quote at (session_id, ts).",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "session_id": {"type": "string"},
                "ts": {"type": "number"},
            },
            "required": ["session_id", "ts"],
        },
    },
}

_SUBMIT_ANSWER_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_answer",
        "description": "Return the final answer with optional chart + citations.",
        "parameters": CustomReportAnswer.model_json_schema(),
    },
}


def answer_custom_report_question(
    *,
    study: Study | None,
    question: str,
    scope_study_ids: list[str] | None = None,
    max_tool_rounds: int = 4,
) -> CustomReportAnswer:
    """Answer one Custom Report / Knowledge Explore question.

    The LLM may call data tools up to ``max_tool_rounds`` times to gather
    evidence before producing ``submit_answer``.

    ``study=None`` means cross-study (Knowledge Explore path).
    ``scope_study_ids`` narrows the tool lookups when non-empty.
    """
    scope_ids = scope_study_ids or ([str(study.id)] if study is not None else [])
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _CUSTOM_REPORT_PROMPT},
        {
            "role": "system",
            "content": (
                "<scope>\n"
                f"study_ids={scope_ids or 'ALL'}\n"
                f"research_goal={study.research_goal if study else '(cross-study)'}\n"
                "</scope>"
            ),
        },
        {"role": "user", "content": question},
    ]

    tools = [
        _AGGREGATE_TAG_TOOL,
        _FILTER_SESSIONS_TOOL,
        _CITE_QUOTE_TOOL,
        _SUBMIT_ANSWER_TOOL,
    ]

    client = get_llm()
    for _round in range(max_tool_rounds):
        completion = client.chat.completions.create(
            model=default_model(), messages=messages, tools=tools
        )
        choice = completion.choices[0]
        tool_calls = getattr(choice.message, "tool_calls", None) or []
        if not tool_calls:
            logger.warning("memai.custom_report.no_tool_call")
            return CustomReportAnswer(
                answer_markdown=choice.message.content
                or "I couldn't produce an answer for that question.",
            )

        for tool_call in tool_calls:
            name = tool_call.function.name
            args_raw = tool_call.function.arguments
            try:
                args = json.loads(args_raw)
            except json.JSONDecodeError:
                args = {}

            if name == "submit_answer":
                try:
                    return CustomReportAnswer.model_validate(args)
                except ValueError as exc:
                    logger.warning("memai.custom_report.submit_parse_failed", extra={"error": str(exc)})
                    return CustomReportAnswer(
                        answer_markdown="I formatted my answer incorrectly; please try again.",
                    )

            # Data tool — execute + feed result back into messages.
            result = _execute_data_tool(name, args, scope_ids)
            messages.append(
                {
                    "role": "assistant",
                    "tool_calls": [tool_call.model_dump()],
                    "content": None,
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    return CustomReportAnswer(
        answer_markdown=(
            "I couldn't finalise an answer within the allowed tool-call budget. "
            "Try narrowing the question or splitting it into sub-questions."
        )
    )


def _execute_data_tool(
    name: str, args: dict[str, Any], scope_ids: list[str]
) -> dict[str, Any]:
    """Dispatch a data tool. Kept here so tests can swap via monkeypatch.

    Real tools query ``SessionInsight``, ``KnowledgeChunk``, etc. For the
    moment these are minimal scaffolds — extend as Analysis grows.
    """
    from merism.models import KnowledgeChunk, SessionInsight as SessionInsightModel

    if name == "aggregate_tag":
        tag_name = str(args.get("tag_name", ""))
        qs = SessionInsightModel.objects.all()
        if scope_ids:
            qs = qs.filter(session__study_id__in=scope_ids)
        counts: dict[str, int] = {}
        for insight in qs.only("tags"):
            value = (insight.tags or {}).get(tag_name)
            if value is None:
                continue
            key = str(value)
            counts[key] = counts.get(key, 0) + 1
        return {"tag": tag_name, "distribution": counts}

    if name == "filter_sessions":
        criteria = args.get("criteria") or {}
        qs = SessionInsightModel.objects.all()
        if scope_ids:
            qs = qs.filter(session__study_id__in=scope_ids)
        ids = [str(s.session_id) for s in qs.only("session_id")]
        return {"criteria": criteria, "session_ids": ids[:100]}

    if name == "cite_quote":
        session_id = str(args.get("session_id", ""))
        ts = float(args.get("ts", 0.0))
        chunk = (
            KnowledgeChunk.objects.filter(
                document__session_id=session_id, document__source_type="session_transcript"
            )
            .order_by("chunk_index")
            .first()
        )
        return {
            "session_id": session_id,
            "ts": ts,
            "quote": chunk.content if chunk else "",
        }

    return {"error": f"unknown tool {name}"}


def _parse_tool_call(completion: Any, schema: type[BaseModel]) -> Any | None:
    tool_calls = getattr(completion.choices[0].message, "tool_calls", None) or []
    if not tool_calls:
        return None
    try:
        return schema.model_validate(json.loads(tool_calls[0].function.arguments))
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("memai.agents.parse_failed", extra={"error": str(exc)})
        return None
