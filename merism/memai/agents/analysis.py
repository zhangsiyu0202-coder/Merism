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
from uuid import uuid4

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

    # Try gateway first (uses reasoner route if configured)
    gw_client = None
    try:
        from merism.llm_gateway.client import sync_get_client

        gw_client = sync_get_client("reasoner", team=session.study.team, trace_id=session.trace_id)
    except Exception:
        pass

    if gw_client:
        completion = gw_client.sync_complete(
            messages=messages,
            tools=[_SUBMIT_INSIGHT_TOOL],
            tool_choice={"type": "function", "function": {"name": "submit_session_insight"}},
        )
    else:
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
    """Answer one Custom Report / Knowledge Explore question via a
    LangGraph tool-loop agent.

    Nodes:
        agent → decide(tool_calls?) → tools → agent ... → submit_answer (END)

    No fallback: graph errors return a generic error answer.
    """
    from asgiref.sync import async_to_sync

    return async_to_sync(_answer_question_async)(
        study=study,
        question=question,
        scope_study_ids=scope_study_ids,
        max_tool_rounds=max_tool_rounds,
    )


# ── LangGraph implementation ────────────────────────────────

async def _answer_question_async(
    *,
    study: Study | None,
    question: str,
    scope_study_ids: list[str] | None = None,
    max_tool_rounds: int = 4,
) -> CustomReportAnswer:
    from langgraph.graph import END, StateGraph
    from typing import TypedDict

    from merism.memai.graph import call_llm_with_tools

    scope_ids = scope_study_ids or ([str(study.id)] if study is not None else [])
    system_messages = [
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
    tools = [_AGGREGATE_TAG_TOOL, _FILTER_SESSIONS_TOOL, _CITE_QUOTE_TOOL, _SUBMIT_ANSWER_TOOL]

    class AgentState(TypedDict, total=False):
        messages: list[dict[str, Any]]
        rounds: int
        final_answer: CustomReportAnswer | None

    async def agent_node(state: AgentState) -> dict[str, Any]:
        """Call the LLM with tool definitions."""
        if study is None:
            # Cross-study without a team → legacy path (no LLM Gateway routing)
            from merism.memai.llm import default_model, get_llm

            client = get_llm(async_=True)
            completion = await client.chat.completions.create(
                model=default_model(), messages=state["messages"], tools=tools,
            )
        else:
            completion = await call_llm_with_tools(
                team=study.team,
                trace_id=uuid4(),
                messages=state["messages"],
                tools=tools,
            )
        choice = completion.choices[0]
        tool_calls = getattr(choice.message, "tool_calls", None) or []
        new_messages = list(state["messages"])

        if not tool_calls:
            # Model gave a plain text response — wrap it as an answer
            return {
                "messages": new_messages,
                "final_answer": CustomReportAnswer(
                    answer_markdown=choice.message.content or "I couldn't produce an answer.",
                ),
            }

        # Append the assistant's tool_calls message so the tool responses
        # can reference them by tool_call_id
        new_messages.append(
            {
                "role": "assistant",
                "tool_calls": [tc.model_dump() for tc in tool_calls],
                "content": None,
            }
        )

        # Check for submit_answer — terminal
        for tc in tool_calls:
            if tc.function.name == "submit_answer":
                try:
                    args = json.loads(tc.function.arguments)
                    return {
                        "messages": new_messages,
                        "final_answer": CustomReportAnswer.model_validate(args),
                    }
                except (json.JSONDecodeError, ValueError) as exc:
                    logger.warning("memai.custom_report.submit_parse_failed: %s", str(exc))
                    return {
                        "messages": new_messages,
                        "final_answer": CustomReportAnswer(
                            answer_markdown="I formatted my answer incorrectly; please try again.",
                        ),
                    }

        # Otherwise → data tools; pass through to tool node
        return {"messages": new_messages, "rounds": state.get("rounds", 0) + 1}

    async def tools_node(state: AgentState) -> dict[str, Any]:
        """Execute all pending data tool calls from the last assistant message."""
        messages = list(state["messages"])
        last = messages[-1]
        tool_call_dicts = last.get("tool_calls", []) if isinstance(last, dict) else []

        for tc in tool_call_dicts:
            name = tc["function"]["name"]
            args_raw = tc["function"]["arguments"]
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
            except json.JSONDecodeError:
                args = {}
            if name == "submit_answer":
                continue  # handled in agent_node
            result = _execute_data_tool(name, args or {}, scope_ids)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
        return {"messages": messages}

    def should_continue(state: AgentState) -> str:
        if state.get("final_answer") is not None:
            return "done"
        if state.get("rounds", 0) >= max_tool_rounds:
            return "done"
        return "tools"

    # Build graph
    g = StateGraph(AgentState)
    g.add_node("agent", agent_node)
    g.add_node("tools", tools_node)
    g.set_entry_point("agent")
    g.add_conditional_edges("agent", should_continue, {"tools": "tools", "done": END})
    g.add_edge("tools", "agent")
    compiled = g.compile()

    initial: AgentState = {"messages": system_messages, "rounds": 0, "final_answer": None}
    try:
        final_state = await compiled.ainvoke(initial, {"recursion_limit": max_tool_rounds * 3 + 5})
    except Exception as exc:  # noqa: BLE001
        logger.warning("memai.custom_report.graph_failed: %s", str(exc))
        return CustomReportAnswer(
            answer_markdown=f"Sorry, I couldn't answer that: {exc}",
        )

    answer = final_state.get("final_answer")
    if answer is None:
        return CustomReportAnswer(
            answer_markdown=(
                "I couldn't finalise an answer within the allowed tool-call budget. "
                "Try narrowing the question or splitting it into sub-questions."
            ),
        )
    return answer


def _OLD_answer_custom_report_question(
    *,
    study: Study | None,
    question: str,
    scope_study_ids: list[str] | None = None,
    max_tool_rounds: int = 4,
) -> CustomReportAnswer:
    """Deprecated — kept commented out as reference. Superseded by the
    LangGraph implementation above."""
    return CustomReportAnswer(answer_markdown="")


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
