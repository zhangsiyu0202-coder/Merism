"""Cleaning pipeline orchestrator.

Public API:

    clean_session_transcript(session) -> list[dict]

Runs all stages in order. Each stage is best-effort — errors are
logged and the stage's input is passed through unchanged.

The legacy two-step (rule_clean → llm_polish) is still available via
:func:`merism.conductor.llm_polish.polish_session_turns`. This module
layers 4 extra stages (glossary, normalize, semantic merge) around it.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from merism.cleaning.stages.stage1_asr_correct import StageContext, correct_with_glossary
from merism.cleaning.stages.stage3_normalize import normalize_text
from merism.models import InterviewSession

logger = logging.getLogger(__name__)


async def clean_session_transcript(
    session: InterviewSession,
    *,
    run_glossary: bool = True,
    run_normalize: bool = True,
    run_polish: bool = True,
    run_merge: bool = False,  # off by default — LLM cost, opt-in
) -> list[dict[str, Any]]:
    """Full cleaning pipeline for a session's raw transcript.

    Returns the cleaned transcript (a list of turn dicts) — does NOT
    persist. Caller writes back to ``session.transcript``.
    """
    turns = [dict(t) for t in (session.transcript or [])]
    if not turns:
        return turns

    context = StageContext(
        team_id=session.team_id,
        study_id=session.study_id,
        session_id=session.id,
        trace_id=getattr(session, "trace_id", None),
    )

    # Stage 1 — ASR glossary
    if run_glossary:
        try:
            turns = await correct_with_glossary(turns, context)
        except Exception:
            logger.exception("cleaning.stage1.failed", extra={"session_id": str(session.id)})

    # Stage 3 — normalize (zh/en mixed, whitespace, NFKC)
    if run_normalize:
        try:
            turns = await normalize_text(turns, context)
        except Exception:
            logger.exception("cleaning.stage3.failed", extra={"session_id": str(session.id)})

    # Stages 4+5 — rule_clean + llm_polish (via existing module)
    if run_polish:
        try:
            from merism.conductor.llm_polish import polish_session_turns

            turns = await polish_session_turns(
                turns,
                team=session.study.team if session.study_id else None,
                trace_id=getattr(session, "trace_id", None),
            )
        except Exception:
            logger.exception("cleaning.stage45.failed", extra={"session_id": str(session.id)})

    # Stage 6 — semantic merge (opt-in, LLM cost)
    if run_merge:
        try:
            from merism.cleaning.stages.stage6_semantic_merge import semantic_merge

            turns = await semantic_merge(turns, context)
        except Exception:
            logger.exception("cleaning.stage6.failed", extra={"session_id": str(session.id)})

    return turns
