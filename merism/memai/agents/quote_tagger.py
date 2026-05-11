"""Quote tagger — attaches deductive + inductive codes to a SessionQuote.

Given a codebook (deductive taxonomy) and a participant quote, the
tagger produces:

- ``deductive``: 0-3 codebook entries matching this quote, each with
  a confidence score.
- ``inductive_suggestions``: 0-2 new codes the tagger proposes when
  the quote carries a pattern not present in the codebook.
- ``sentiment``: positive / negative / neutral / mixed.
- ``action_type``: suggestion / complaint / praise / question / null.

Writes the result to ``SessionQuote.tags``. Idempotent: skips a quote
whose ``tags`` already includes a ``deductive`` key.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from asgiref.sync import sync_to_async
from pydantic import BaseModel, ConfigDict, Field

from merism.memai.llm import LLMUnavailableError, default_model, get_llm
from merism.models import SessionQuote, Study

logger = logging.getLogger(__name__)


# ── Output schema ─────────────────────────────────────────────

class DeductiveMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code_id: str
    confidence: float = Field(ge=0.0, le=1.0)


class InductiveSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=64)
    rationale: str = Field(max_length=200)


class TaggedQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deductive: list[DeductiveMatch] = Field(default_factory=list, max_length=4)
    inductive_suggestions: list[InductiveSuggestion] = Field(
        default_factory=list, max_length=3
    )
    sentiment: Literal["positive", "negative", "neutral", "mixed"] = "neutral"
    action_type: Literal["suggestion", "complaint", "praise", "question"] | None = None


SYSTEM_PROMPT = """\
You are a qualitative coder. Given a participant quote + a codebook
(list of predefined codes), you produce analytical tags.

Deductive coding:
- Check which codebook entries the quote matches. Return at most 3 of
  the best matches, each with a ``confidence`` 0.0-1.0.
- ``confidence`` >= 0.7 means unambiguous match.
- ``confidence`` 0.4-0.6 means plausible but borderline.
- Never return matches below 0.3.
- A quote can match zero codes — if nothing fits, return empty.

Inductive coding:
- If the quote expresses a pattern NOT covered by the codebook, suggest
  a new code (1-3 word ``snake_case`` code + one-sentence ``rationale``).
- At most 2 suggestions per quote.
- Do NOT duplicate existing codebook entries as suggestions.

Sentiment:
- positive / negative / neutral / mixed — pick exactly one.

Action type (null if none of the four fits):
- ``suggestion`` — participant proposes a change.
- ``complaint`` — expresses frustration, dissatisfaction.
- ``praise`` — expresses approval, satisfaction.
- ``question`` — asks something the researcher/product should answer.

Output JSON only: ``{"deductive": [...], "inductive_suggestions": [...],
"sentiment": "...", "action_type": null}``.
"""


async def tag_quote(quote: SessionQuote, study: Study) -> dict[str, Any]:
    """Tag a single quote. Returns the tags dict + persists to DB.

    Idempotent: if ``quote.tags`` already has a ``deductive`` key, we
    return the existing tags without invoking the LLM.
    """
    if isinstance(quote.tags, dict) and "deductive" in quote.tags:
        return dict(quote.tags)

    codebook: list[dict[str, Any]] = list(study.codebook or [])
    payload = {
        "quote": quote.text,
        "codebook": [
            {"code_id": c["code_id"], "name": c.get("name", ""), "description": c.get("description", "")}
            for c in codebook
        ],
    }

    try:
        client = get_llm(async_=True)
        completion = await client.chat.completions.create(
            model=default_model(),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        raw = completion.choices[0].message.content or "{}"
        parsed = TaggedQuote.model_validate_json(raw)
    except (LLMUnavailableError, Exception) as exc:  # noqa: BLE001
        logger.warning(
            "quote_tagger.llm_failed",
            extra={"error": str(exc), "quote_id": str(quote.id)},
        )
        return dict(quote.tags or {})

    # Filter deductive matches to codes that actually exist in the codebook.
    known_ids = {c["code_id"] for c in codebook}
    deductive = [
        {"code_id": m.code_id, "confidence": m.confidence}
        for m in parsed.deductive
        if m.code_id in known_ids
    ]
    inductive = [
        {"code": s.code, "rationale": s.rationale} for s in parsed.inductive_suggestions
    ]

    new_tags: dict[str, Any] = dict(quote.tags or {})
    new_tags["deductive"] = deductive
    new_tags["inductive_suggestions"] = inductive
    new_tags["sentiment"] = parsed.sentiment
    new_tags["action_type"] = parsed.action_type

    quote.tags = new_tags
    await _asave(quote)
    return new_tags


async def tag_quotes_for_session(
    quotes: list[SessionQuote], study: Study
) -> list[dict[str, Any]]:
    """Tag every quote for a session sequentially. Returns the tag
    dicts in the same order. Errors on individual quotes are logged
    and skipped — the method never raises.
    """
    results: list[dict[str, Any]] = []
    for quote in quotes:
        tags = await tag_quote(quote, study)
        results.append(tags)
    return results


async def promote_inductive_suggestions(
    study: Study, min_occurrences: int = 2
) -> int:
    """Merge inductive suggestions that appear ``min_occurrences`` or more
    times across the study's quotes into ``study.codebook`` with
    ``source=inductive``. Returns the number of codes added.

    This turns "the tagger proposed these codes" into "the codebook now
    contains them" once we see them recurring. Researchers can still
    edit the codebook manually via the API.
    """
    rows = await _aget_quotes_for_study(study)
    counts: dict[str, list[str]] = {}
    for row in rows:
        for sug in (row.tags or {}).get("inductive_suggestions", []):
            code = sug.get("code", "").strip()
            if not code:
                continue
            counts.setdefault(code, []).append(sug.get("rationale", ""))

    existing_ids = {c["code_id"] for c in (study.codebook or [])}
    added = 0
    new_codebook = list(study.codebook or [])
    for code, rationales in counts.items():
        if len(rationales) < min_occurrences:
            continue
        if code in existing_ids:
            continue
        new_codebook.append(
            {
                "code_id": code,
                "name": code.replace("_", " ").title(),
                "description": rationales[0][:200] if rationales else "",
                "examples": [],
                "source": "inductive",
            }
        )
        added += 1

    if added:
        study.codebook = new_codebook
        await _asave_study(study)
    return added


# ── DB helpers ──

@sync_to_async
def _asave(quote: SessionQuote) -> None:
    quote.save(update_fields=["tags", "updated_at"])


@sync_to_async
def _asave_study(study: Study) -> None:
    study.save(update_fields=["codebook", "updated_at"])


@sync_to_async
def _aget_quotes_for_study(study: Study) -> list[SessionQuote]:
    return list(SessionQuote.objects.filter(study=study))
