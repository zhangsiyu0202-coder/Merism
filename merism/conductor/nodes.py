"""LangGraph nodes for the v3 conductor.

Pattern provenance: design.md §0 / pattern 5. Each node has the canonical
LangGraph shape ``(state, config: RunnableConfig) -> dict``. LLM construction
happens **inside** the node (never at module top), so per-call model /
temperature / API base swaps work without process restart.

Per AGENTS.md Rule 4 — at most 1 LLM call per turn (the judge), 0 calls
per session bracket. Final-report generation is delegated to the existing
post-session pipeline (``merism.conductor.post_session`` /
``SessionInsight`` agents). probe_instruction is passed to the judge prompt
verbatim — no session-start rewriting.

Per Rule 12 — no LLM call inside any routing function. Routing lives in
``graph.py`` as pure ``state -> Literal[...]`` dispatch.

Per Req 25 — every LLM call wraps in ``try/except`` and degrades to
``sufficient=True`` (judges). Engine never raises out of node functions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal, cast

from langgraph.types import interrupt

from merism.conductor.configuration import Configuration
from merism.conductor.llm import build_evaluator, build_llm
from merism.conductor.prompts import JUDGE_DEEP_PROMPT, JUDGE_STANDARD_PROMPT
from merism.conductor.schema import Outline, Question, Section, Turn
from merism.conductor.state import AdvanceOutput, JudgeOutput, OverallState
from merism.conductor.tools_and_schemas import Evaluation

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════════════════════════


def _outline_from_state(state: OverallState) -> Outline:
    """Reload the outline Pydantic model from the JSON dict in state."""
    if "outline" not in state:
        raise RuntimeError("OverallState missing 'outline' — runner must initialize it at session start")
    return Outline.model_validate(state["outline"])


def _current_section_and_question(state: OverallState) -> tuple[Section, Question]:
    """Resolve current cursor position to (Section, Question) pair."""
    outline = _outline_from_state(state)
    section_i = state.get("section_i", 0)
    question_i = state.get("question_i", 0)
    section = outline.sections[section_i]
    question = section.questions[question_i]
    return section, question


def _format_transcript_tail(state: OverallState, n: int = 6) -> str:
    """Last ``n`` turns formatted for inclusion in a judge prompt."""
    turns: list[Turn] = list(state.get("transcript", []))[-n:]
    if not turns:
        return "(no prior turns)"
    lines: list[str] = []
    for t in turns:
        lines.append(f"Q ({t['kind']}): {t['question']}")
        lines.append(f"A: {t['answer']}")
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════
#  ask_and_wait — emits question, interrupts for participant reply
# ════════════════════════════════════════════════════════════════════


def ask_and_wait(state: OverallState, config: RunnableConfig) -> dict:
    """Speak the current question (or pending probe), then ``interrupt()``.

    On resume (``Command(resume=user_text)``), the ``interrupt()`` call
    returns the user's text. We append a single :class:`Turn` to the
    transcript via the ``operator.add`` reducer (return list of one).
    """
    section, qspec = _current_section_and_question(state)
    pending = state.get("pending_probe")
    question_text = pending or qspec.ask
    kind: Literal["main", "followup"] = "followup" if pending else "main"

    answer = interrupt(
        {
            "type": "question",
            "section_id": section.id,
            "question_id": qspec.id,
            "kind": kind,
            "question": question_text,
        }
    )

    new_turn: Turn = {
        "section_id": section.id,
        "question_id": qspec.id,
        "kind": kind,
        "question": question_text,
        "answer": str(answer),
    }
    return {
        "last_answer": str(answer),
        "transcript": [new_turn],
    }


# ════════════════════════════════════════════════════════════════════
#  judge_off — no LLM call; always sufficient
# ════════════════════════════════════════════════════════════════════


def judge_off(state: OverallState, config: RunnableConfig) -> JudgeOutput:
    """Skip-judge mode (Req 7). Never calls the LLM. Always advances."""
    return {
        "pending_probe": None,
        "last_evaluation": {"sufficient": True, "skipped": True},
    }


# ════════════════════════════════════════════════════════════════════
#  judge_standard / judge_deep — 1 LLM call each, shared helper
# ════════════════════════════════════════════════════════════════════


def judge_standard(state: OverallState, config: RunnableConfig) -> JudgeOutput:
    """Lenient judge: replied to the question → sufficient. Budget = ``standard_followups``."""
    cfg = Configuration.from_runnable_config(config)
    return _judge_with_prompt(state, config, JUDGE_STANDARD_PROMPT, max_followups=cfg.standard_followups)


def judge_deep(state: OverallState, config: RunnableConfig) -> JudgeOutput:
    """Strict judge: needs concrete detail. Budget = ``deep_followups``."""
    cfg = Configuration.from_runnable_config(config)
    return _judge_with_prompt(state, config, JUDGE_DEEP_PROMPT, max_followups=cfg.deep_followups)


def _judge_with_prompt(
    state: OverallState,
    config: RunnableConfig,
    template: str,
    *,
    max_followups: int,
) -> JudgeOutput:
    """Shared logic for judge_standard / judge_deep.

    Reads ``probe_instruction`` directly from the question (verbatim text
    researcher wrote). On LLM failure, return ``sufficient=True`` so the
    engine advances rather than hangs (Req 25).

    Budget (``max_followups``) is supplied by the caller, sourced from
    ``Configuration`` (mode-specific). Researchers do not set this per
    question — the mode picks the budget.
    """
    cfg = Configuration.from_runnable_config(config)
    _, qspec = _current_section_and_question(state)
    probe_count = state.get("probe_count", 0)

    try:
        llm = build_llm(cfg.judge_model, temperature=cfg.judge_temperature)
        evaluator = build_evaluator(llm, Evaluation)
        prompt = template.format(
            ask=qspec.ask,
            probe_instruction=qspec.probe_instruction or "(none)",
            transcript_tail=_format_transcript_tail(state, n=6),
            answer=state.get("last_answer", ""),
        )
        ev = cast(Evaluation, evaluator.invoke(prompt))
    except Exception:
        logger.exception("conductor.judge.failed")
        return {
            "pending_probe": None,
            "last_evaluation": {"sufficient": True, "reason": "judge_unavailable"},
            "last_error": "judge_call_failed",
        }

    should_probe = not ev.sufficient and bool(ev.followup) and probe_count < max_followups
    if should_probe:
        return {
            "pending_probe": ev.followup,
            "probe_count": probe_count + 1,
            "last_evaluation": ev.model_dump(),
        }
    return {
        "pending_probe": None,
        "last_evaluation": ev.model_dump(),
    }


# ════════════════════════════════════════════════════════════════════
#  advance_cursor — pure-function cursor progression
# ════════════════════════════════════════════════════════════════════


def advance_cursor(state: OverallState, config: RunnableConfig) -> AdvanceOutput:
    """Move cursor to next question. Cross section boundaries. Mark done at end."""
    outline = _outline_from_state(state)
    section_i = state.get("section_i", 0)
    question_i = state.get("question_i", 0)
    current_questions = outline.sections[section_i].questions

    if question_i + 1 < len(current_questions):
        return {
            "question_i": question_i + 1,
            "pending_probe": None,
            "probe_count": 0,
        }
    if section_i + 1 < len(outline.sections):
        return {
            "section_i": section_i + 1,
            "question_i": 0,
            "pending_probe": None,
            "probe_count": 0,
        }
    return {
        "done": True,
        "pending_probe": None,
        "probe_count": 0,
    }


__all__ = [
    "advance_cursor",
    "ask_and_wait",
    "judge_deep",
    "judge_off",
    "judge_standard",
]
