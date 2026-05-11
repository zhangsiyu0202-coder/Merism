"""LLM-based intelligent-verbatim polish.

After :mod:`merism.conductor.rule_clean` has stripped the obvious
fillers, this module sends the whole session's turns in a **single**
DeepSeek call to apply light grammar polish while preserving every
factual detail.

Key design decisions:

1. **Batch per session, not per turn.** Context helps the model keep
   voice consistent across turns, and one round-trip is cheaper than N.
2. **Strict preserve-meaning prompt.** We instruct the model to fix
   grammar / readability ONLY. Never add new content, never drop
   content. Unsure → keep original.
3. **Array length parity is enforced** by the Pydantic output schema
   plus a server-side length assert. If the model returns the wrong
   number of turns, we reject its entire output and fall back to the
   rule-cleaned input.
4. **Participant turns only** are polished by default. Agent turns
   (AI moderator) are already fluent and don't need polish — we pass
   them through unchanged to avoid double-generation artefacts.

Test path:
    Use :class:`merism.testing.fakes.DeterministicLLM` to stub the
    DeepSeek response. Tests under ``tests/test_llm_polish.py``.
"""

from __future__ import annotations

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from merism.conductor.rule_clean import rule_clean
from merism.memai.llm import LLMUnavailableError, default_model, get_llm

logger = logging.getLogger(__name__)

# ── Pydantic schemas for structured LLM output ────────────────

class PolishedTurn(BaseModel):
    """One polished transcript turn."""

    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0, description="Matches the input turn index.")
    text_clean: str = Field(description="Polished text for this turn.")


class PolishedBatch(BaseModel):
    """The full batch response — one element per input turn."""

    model_config = ConfigDict(extra="forbid")

    turns: list[PolishedTurn]

    @field_validator("turns")
    @classmethod
    def _dedupe_indices(cls, value: list[PolishedTurn]) -> list[PolishedTurn]:
        seen: set[int] = set()
        for t in value:
            if t.index in seen:
                raise ValueError(f"duplicate index {t.index}")
            seen.add(t.index)
        return value


# ── Prompt ─────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a transcript editor applying "intelligent verbatim" rules to an
interview transcript. Your one and only job is to improve readability
while preserving every factual detail of what the speaker said.

Rules (non-negotiable):
1. PRESERVE MEANING EXACTLY. Never add or remove content. Never change
   numbers, names, product mentions, or any opinion the speaker
   expressed. If unsure, keep the original wording.
2. Fix obvious grammar and fluency issues only. Examples:
     - Subject-verb agreement: "they was" → "they were".
     - Broken sentence structure from ASR: reorder to the minimum
       extent that makes the sentence grammatical.
     - Obvious ASR word confusion: "their" ↔ "there", 的/地/得 in
       Chinese — fix only when the correct form is unambiguous.
3. Never paraphrase. Never summarise. Never translate.
4. Keep the speaker's register (casual stays casual, formal stays formal).
5. Keep all emotion words, hedges that carry meaning ("I think",
   "maybe", "I'm not sure"), and direct quotes. These are research data.
6. Do NOT add punctuation that implies emotion the speaker didn't express
   (no adding exclamation marks).

Input format: a JSON array of turns, each with ``index`` and ``text``.
Output format: a JSON object ``{"turns": [{"index": N, "text_clean": "..."}]}``
with one entry per input turn, in the same order, same indices.
"""


# ── Public API ─────────────────────────────────────────────────

async def polish_session_turns(
    turns: list[dict[str, Any]],
    *,
    polish_roles: tuple[str, ...] = ("participant",),
    team: Any | None = None,
    trace_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """Polish a whole session's turns. Returns the same list shape with
    ``text_raw`` + ``text_clean`` populated on every turn.

    Strategy:
        - Every turn gets ``text_raw`` = original text.
        - Every turn runs through :func:`rule_clean` first.
        - Turns whose role is in ``polish_roles`` AND have non-trivial
          content go into the batch LLM call for intelligent verbatim.
        - Agent / system turns get ``text_clean`` = rule-cleaned text.
        - On LLM failure, everyone gets ``text_clean`` = rule-cleaned
          text. No turn is left with empty ``text_clean``.
    """
    if not turns:
        return []

    # Pass 1: rule_clean every turn; record raw + candidate.
    pre: list[dict[str, Any]] = []
    for turn in turns:
        raw = turn.get("text_raw") or turn.get("text", "")
        pre_clean = rule_clean(str(raw))
        pre.append({**turn, "text_raw": raw, "_pre_clean": pre_clean})

    # Pass 2: collect indices that need LLM polish.
    to_polish: list[tuple[int, str]] = []
    for idx, turn in enumerate(pre):
        if turn.get("role") not in polish_roles:
            continue
        if not turn["_pre_clean"]:
            continue
        # Skip ultra-short ("ok" / "yes") — nothing to polish.
        if len(turn["_pre_clean"]) < 6:
            continue
        to_polish.append((idx, turn["_pre_clean"]))

    polished_by_index: dict[int, str] = {}
    if to_polish:
        try:
            polished_by_index = await _llm_polish_batch(to_polish, team=team, trace_id=trace_id)
        except (LLMUnavailableError, Exception) as exc:  # noqa: BLE001
            # Fall back to rule-clean on any failure. Log but don't raise —
            # a session never fails to process because of LLM issues.
            logger.warning(
                "transcript.polish.llm_failed",
                extra={"error": str(exc), "turn_count": len(to_polish)},
            )
            polished_by_index = {}

    # Pass 3: assemble the final transcript.
    out: list[dict[str, Any]] = []
    for idx, turn in enumerate(pre):
        text_clean = polished_by_index.get(idx, turn["_pre_clean"])
        # Legacy ``text`` stays populated — it mirrors clean now.
        out.append(
            {
                **{k: v for k, v in turn.items() if k != "_pre_clean"},
                "text_clean": text_clean,
                "text": text_clean or turn["_pre_clean"] or turn.get("text", ""),
            }
        )
    return out


async def _llm_polish_batch(
    items: list[tuple[int, str]],
    *,
    team: Any | None = None,
    trace_id: UUID | None = None,
) -> dict[int, str]:
    """Call DeepSeek with the batched polish prompt. Returns a mapping
    ``{input_index: polished_text}``. Raises on parse / schema / LLM error.
    """
    payload = [{"index": idx, "text": text} for idx, text in items]
    user_message = json.dumps(payload, ensure_ascii=False)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    # Try gateway first, fall back to legacy get_llm()
    completion = None
    if team and trace_id:
        try:
            from merism.llm_gateway.client import get_client

            gw_client = await get_client("chat", team=team, trace_id=trace_id)
            response = await gw_client.complete(
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            raw = response.choices[0].message.content or "{}"
            completion = raw
        except Exception:
            completion = None

    if completion is None:
        client = get_llm(async_=True)
        response = await client.chat.completions.create(
            model=default_model(),
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        completion = response.choices[0].message.content or "{}"

    raw = completion
    parsed = PolishedBatch.model_validate_json(raw)

    # Length parity check: if the model missed a turn, fall back for
    # the whole batch — we don't want to silently mix polished + pre-clean.
    input_indices = {idx for idx, _ in items}
    output_indices = {t.index for t in parsed.turns}
    if input_indices != output_indices:
        raise ValueError(
            "LLM output index set mismatch: "
            f"expected {sorted(input_indices)}, got {sorted(output_indices)}"
        )

    return {t.index: t.text_clean for t in parsed.turns}
