"""Outline Review Agent — PRODUCT.md §5.1.

Conversational; one LLM call per researcher turn. Returns
``reply_markdown`` + ``proposed_changes[]`` via function calling.
``proposed_changes`` is a proposal — the researcher accepts each
individually via :func:`apply_proposed_changes`.

Review axes (Req 5.4):
1. privacy / PII       2. ordering (warmup→core→closing)
3. structure           4. bias (leading, double-barrelled)
5. alignment w/ goal   6. followup_depth reasonableness

Never rewrite silently; always end replies with a question for the
researcher (``awaiting_user_decision=True``).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from merism.memai.llm import default_model, get_llm

logger = logging.getLogger(__name__)


class ModifyQuestionOp(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["modify_question"]
    question_id: str
    new_text: str
    reason: str = ""


class InsertQuestionOp(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["insert_question"]
    after_question_id: str
    new_question: dict[str, Any]
    reason: str = ""


class RemoveQuestionOp(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["remove_question"]
    question_id: str
    reason: str = ""


ProposedChange = ModifyQuestionOp | InsertQuestionOp | RemoveQuestionOp


class OutlineReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply_markdown: str = Field(..., description="Conversational reply to the researcher.")
    proposed_changes: list[ProposedChange] = Field(default_factory=list)
    awaiting_user_decision: bool = True


SYSTEM_PROMPT = """\
You are a research-methods reviewer helping a researcher improve their
interview outline before participants see it. You never silently rewrite;
you surface concerns and propose specific, minimal edits the researcher
approves one-by-one.

Review dimensions (cover each when relevant):
1. Privacy / PII — flag income / age / employer / health questions unless
   they directly serve the research_goal.
2. Ordering — warmup → core → closing. Flag questions jumping into deep
   territory too early.
3. Structure — section titles, question grouping.
4. Bias — leading ("wouldn't you agree…?"), double-barrelled, suggestive.
5. Alignment with research_goal.
6. Follow-up depth — yes/no rarely needs depth > 1; open "why" merits 2-3.

Response contract:
- Always finish with a question to the researcher. Do NOT make decisions.
- Produce proposed_changes ONLY when you have a concrete edit ready.
- If you're just asking clarifying questions, return an empty list.
"""


SUBMIT_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_review",
        "description": (
            "Return the review reply plus any proposed changes. Use this for "
            "EVERY response, even if proposed_changes is empty."
        ),
        "parameters": OutlineReviewResponse.model_json_schema(),
    },
}


def review_outline(
    *,
    research_goal: str,
    guide_sections: list[dict[str, Any]],
    chat_history: list[dict[str, str]],
    researcher_message: str,
) -> OutlineReviewResponse:
    """One review turn — sync call (short reply, atomic-apply changes)."""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": _context_prompt(research_goal, guide_sections)},
    ]
    # Recent chat window — keep cost bounded.
    for turn in chat_history[-12:]:
        messages.append(turn)
    messages.append({"role": "user", "content": researcher_message})

    client = get_llm()
    completion = client.chat.completions.create(
        model=default_model(),
        messages=messages,
        tools=[SUBMIT_TOOL],
        tool_choice={"type": "function", "function": {"name": "submit_review"}},
    )

    choice = completion.choices[0]
    tool_calls = getattr(choice.message, "tool_calls", None) or []
    if not tool_calls:
        logger.warning("memai.outline_review.no_tool_call")
        return OutlineReviewResponse(
            reply_markdown=choice.message.content or "I wasn't able to generate a review.",
        )
    try:
        payload = json.loads(tool_calls[0].function.arguments)
        return OutlineReviewResponse.model_validate(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("memai.outline_review.parse_failed", extra={"error": str(exc)})
        return OutlineReviewResponse(
            reply_markdown="I had trouble formatting my review. Could you ask again?",
        )


def _context_prompt(research_goal: str, sections: list[dict[str, Any]]) -> str:
    return (
        "<research_goal>\n"
        f"{research_goal.strip()}\n"
        "</research_goal>\n\n"
        "<current_outline>\n"
        f"{json.dumps(sections, ensure_ascii=False, indent=2)}\n"
        "</current_outline>\n"
    )


def apply_proposed_changes(
    guide_sections: list[dict[str, Any]],
    changes: list[ProposedChange],
) -> list[dict[str, Any]]:
    """Apply accepted changes; return a new sections list. Pure function.

    Skips (+ logs) ops that can't be applied (anchor question missing, etc.)
    rather than raising — the researcher expects best-effort apply.
    """
    out = [{**s, "questions": [dict(q) for q in s.get("questions", [])]} for s in guide_sections]
    for change in changes:
        try:
            if change.op == "modify_question":
                _modify(out, change.question_id, change.new_text)
            elif change.op == "insert_question":
                _insert(out, change.after_question_id, change.new_question)
            elif change.op == "remove_question":
                _remove(out, change.question_id)
        except _OpFailed as exc:
            logger.warning("memai.outline_review.apply_skipped", extra={"reason": str(exc)})
    return out


class _OpFailed(Exception):
    pass


def _modify(sections: list[dict[str, Any]], question_id: str, new_text: str) -> None:
    for section in sections:
        for question in section.get("questions", []):
            if question.get("id") == question_id:
                question["text"] = new_text
                return
    raise _OpFailed(f"modify: {question_id} not found")


def _insert(
    sections: list[dict[str, Any]], after_id: str, new_question: dict[str, Any]
) -> None:
    for section in sections:
        qs = section.get("questions", [])
        for i, q in enumerate(qs):
            if q.get("id") == after_id:
                qs.insert(i + 1, new_question)
                return
    raise _OpFailed(f"insert: anchor {after_id} not found")


def _remove(sections: list[dict[str, Any]], question_id: str) -> None:
    for section in sections:
        qs = section.get("questions", [])
        for i, q in enumerate(qs):
            if q.get("id") == question_id:
                del qs[i]
                return
    raise _OpFailed(f"remove: {question_id} not found")
