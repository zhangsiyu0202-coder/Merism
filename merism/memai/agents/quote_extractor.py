"""Quote extractor — the first analytical pass after transcript polish.

Given a completed + cleaned interview session, this agent reads the
polished transcript and extracts 3-10 participant quotes that are
worth preserving as research data. The output is persisted as
:class:`merism.models.SessionQuote` rows so downstream agents (tagger,
insight generator) can attach analytical labels to them.

Selection criteria given to the LLM:
1. Prefer concrete, specific statements over abstract/generic ones.
2. Prefer quotes that answer the current ``question_id``'s intent.
3. Include at least one quote per unique ``question_id`` when possible.
4. Prefer quotes expressing opinion, emotion, or a clear action.
5. Never include agent turns — only participant voice.

Runs once per session and is idempotent: if the session already has
SessionQuote rows, the agent returns the existing list without
invoking the LLM.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from asgiref.sync import sync_to_async
from pydantic import BaseModel, ConfigDict, Field

from merism.conductor.transcript_helpers import get_turn_text, normalize_turn_role
from merism.memai.llm import LLMUnavailableError, default_model, get_llm
from merism.models import InterviewSession, SessionQuote

logger = logging.getLogger(__name__)


# ── Output schemas ─────────────────────────────────────────────

class ExtractedQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Index into the participant-turn-only list we send to the LLM.
    turn_ref: int = Field(ge=0)
    text: str = Field(min_length=3, max_length=2000)
    importance: float = Field(ge=0.0, le=1.0, default=0.5)
    reason: str = Field(default="", max_length=200)


class ExtractedQuotes(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quotes: list[ExtractedQuote] = Field(min_length=0, max_length=15)


SYSTEM_PROMPT = """\
You are a qualitative research assistant. You receive a participant's
cleaned transcript from one interview session. Your job is to extract
3-10 quotes that are worth preserving as research data.

Criteria:
- Concrete, specific statements. Skip "yes/no" or vague noise.
- Quotes that carry opinion, emotion, action, or insight.
- When the participant gave a story or example, prefer the key moment.
- Include at least one quote for each meaningful topic shift.
- Never invent content. Only use text that appears verbatim in the
  input turns.

Input format: JSON array of ``{"turn_ref": N, "text": "..."}``. Only
participant turns are included; agent / moderator turns are already
filtered out.

Output format: ``{"quotes": [{"turn_ref": N, "text": "...",
"importance": 0.0-1.0, "reason": "..."}]}``.

Rules:
- ``turn_ref`` must point to the input turn the quote was drawn from.
  Multiple quotes can share a ``turn_ref`` (one long turn may contain
  multiple quotable lines).
- ``text`` must be an exact or near-exact substring of that turn — do
  not paraphrase.
- ``importance`` rates how central this quote is to understanding the
  participant. 0.2 = routine, 0.5 = notable, 0.8+ = a headline quote.
- ``reason`` is an optional short label like "purchase_intent" or
  "onboarding_friction" — not required but helps later tagging.
- Return empty list ``{"quotes": []}`` only if the transcript had no
  substantive participant content.
"""


async def extract_quotes(session: InterviewSession) -> list[SessionQuote]:
    """Extract high-value participant quotes from a session's transcript.

    Idempotent: returns existing rows if any SessionQuote exists for
    this session.
    """
    existing = await _aget_existing_quotes(session)
    if existing:
        return existing

    transcript = list(session.transcript or [])
    # Index-preserving filter — keep the original indices so we can
    # back-reference turn_indices on SessionQuote.
    participant_turns: list[tuple[int, dict[str, Any]]] = [
        (idx, turn)
        for idx, turn in enumerate(transcript)
        if normalize_turn_role(turn.get("role")) == "participant"
    ]
    if not participant_turns:
        return []

    # Build a compact list for the LLM — {turn_ref, text}.
    payload = [
        {"turn_ref": ref, "text": get_turn_text(turn, "clean")}
        for ref, (_, turn) in enumerate(participant_turns)
        if get_turn_text(turn, "clean")
    ]
    if not payload:
        return []

    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        # Try gateway first
        gw_client = None
        try:
            from merism.llm_gateway.client import get_client

            gw_client = await get_client("chat", team=session.team, trace_id=session.trace_id)
        except Exception:
            pass

        if gw_client:
            response = await gw_client.complete(
                messages=messages, response_format={"type": "json_object"}, temperature=0.2,
            )
            raw = response.choices[0].message.content or "{}"
        else:
            client = get_llm(async_=True)
            completion = await client.chat.completions.create(
                model=default_model(),
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            raw = completion.choices[0].message.content or "{}"
        parsed = ExtractedQuotes.model_validate_json(raw)
    except (LLMUnavailableError, Exception) as exc:
        logger.warning(
            "quote_extractor.llm_failed",
            extra={"error": str(exc), "session_id": str(session.id)},
        )
        return []

    rows = await _persist_quotes(session, parsed.quotes, participant_turns, transcript)
    logger.info(
        "quote_extractor.done",
        extra={"session_id": str(session.id), "quote_count": len(rows)},
    )
    return rows


@sync_to_async
def _aget_existing_quotes(session: InterviewSession) -> list[SessionQuote]:
    return list(SessionQuote.objects.filter(session=session))


@sync_to_async
def _persist_quotes(
    session: InterviewSession,
    quotes: list[ExtractedQuote],
    participant_turns: list[tuple[int, dict[str, Any]]],
    full_transcript: list[dict[str, Any]],
) -> list[SessionQuote]:
    """Write SessionQuote rows to DB, mapping turn_ref → original turn index."""
    rows: list[SessionQuote] = []
    for q in quotes:
        if q.turn_ref >= len(participant_turns):
            logger.debug(
                "quote_extractor.ref_out_of_range",
                extra={"turn_ref": q.turn_ref, "max": len(participant_turns)},
            )
            continue
        orig_idx, turn = participant_turns[q.turn_ref]
        ts_start_ms = int(float(turn.get("ts") or 0.0) * 1000)
        # End ts = next turn's start (if any) else same + 5s buffer.
        next_turn = (
            full_transcript[orig_idx + 1] if orig_idx + 1 < len(full_transcript) else None
        )
        ts_end_ms = (
            int(float(next_turn.get("ts") or 0.0) * 1000) if next_turn else ts_start_ms + 5000
        )

        rows.append(
            SessionQuote.objects.create(
                team=session.team,
                study=session.study,
                session=session,
                text=q.text.strip(),
                turn_indices=[orig_idx],
                ts_start_ms=ts_start_ms,
                ts_end_ms=max(ts_end_ms, ts_start_ms + 500),
                question_id=str(turn.get("question_id") or ""),
                concept_id=str(turn.get("concept_id") or ""),
                importance=q.importance,
                tags={"extractor_reason": q.reason} if q.reason else {},
            )
        )
    return rows
