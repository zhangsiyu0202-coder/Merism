"""Merism interview conductor — single LangGraph engine.

Per ADR 0012 (LangGraph engine, 2026-05-22) and ADR 0013 (v1 retirement,
2026-05-23). The conductor_v3 package was merged in here on 2026-05-24,
so this directory now holds **everything** moderator-related:

Engine (``ask → judge → advance`` graph)
    - ``schema``     — Outline / Section / Question / Turn Pydantic + helpers
    - ``state``      — LangGraph TypedDict + reducer
    - ``configuration`` — runtime knobs (model / temperature / deep multiplier)
    - ``tools_and_schemas`` — Pydantic contracts for LLM structured output
    - ``prompts``    — module-level prompt templates
    - ``llm``        — ChatOpenAI factory with DeepSeek json_mode
    - ``nodes``      — prepare_session / ask_and_wait / judge_off / judge_standard /
                       judge_deep / advance_cursor / finish_interview
    - ``graph``      — StateGraph wiring + PostgresSaver
    - ``runner``     — start_interview / answer_interview / get_interrupt_payload
    - ``persistence`` — bridge: final transcript → InterviewSession.transcript
    - ``factory``    — process-wide compiled graph + checkpointer
    - ``text_adapter`` — HTTP one-turn-per-request adapter
    - ``session_outline`` — guide_snapshot accessor
    - ``configuration`` — runtime config

Post-processing (orchestrators that run **after** a session completes)
    - ``post_session`` — async insight + cleaning orchestration
    - ``transcript_helpers`` — used by quote_extractor + post_session
    - ``llm_polish`` — transcript polishing
    - ``rule_clean`` — non-LLM cleanup rules

Django glue (always imported via ``apps.MerismConfig.ready``)
    - ``signals`` — InterviewSession.completed → enqueue post-session chain
    - ``study_closure_signal`` — Participation.completed → maybe close Study
    - ``inbox_signals`` — fan-out new completions to the inbox
    - ``tasks`` — Celery tasks for transcript polishing + post-session

There is no engine selector. ``Outline.version: Literal["v3"]`` is a
**content-schema discriminator** kept for forward compatibility (a v4
shape could be introduced later); it is not an engine version.
"""

from __future__ import annotations

__all__: list[str] = []
