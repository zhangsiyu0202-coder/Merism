"""InductiveCodeSuggester — batch discovers emergent codes from a session's quotes.

Unlike the per-quote inductive hints in quote_tagger.py, this agent looks at
ALL quotes from a session together and identifies patterns NOT covered by the
existing codebook. Uses a RAG-style check (inspired by GATOS workflow) to
avoid proposing near-duplicates of existing codes.

Single LLM call, structured JSON output.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from merism.memai.llm import LLMUnavailableError, default_model, get_llm
from merism.models import SessionQuote, Study

logger = logging.getLogger(__name__)


class SuggestedCode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=300)
    evidence_quotes: list[str] = Field(default_factory=list, max_length=5)
    rationale: str = Field(max_length=300)


class SuggestionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suggestions: list[SuggestedCode] = Field(default_factory=list, max_length=5)


SYSTEM_PROMPT = """\
You are a qualitative research methodologist performing inductive coding.

Given a batch of participant quotes from one interview session AND the
study's existing codebook, identify emergent patterns NOT already covered.

Rules:
1. Only suggest codes for patterns that appear in 2+ quotes from this batch.
2. Do NOT suggest codes that duplicate or near-duplicate existing codebook
   entries. Check each candidate against the codebook before including it.
3. Each suggestion needs a snake_case code_id, Title Case name, one-sentence
   description, and 1-3 evidence quotes (verbatim short excerpts).
4. Maximum 5 suggestions per session. Quality over quantity.
5. If the existing codebook already covers all patterns, return empty list.
6. Rationale should explain WHY this pattern is distinct from existing codes.

Output JSON: {"suggestions": [{code_id, name, description, evidence_quotes, rationale}]}
"""


async def suggest_codes(
    quotes: list[SessionQuote], study: Study
) -> list[dict[str, Any]]:
    """Analyze session quotes and suggest new codes. Returns list of suggestion dicts."""
    if not quotes:
        return []

    codebook: list[dict[str, Any]] = list(study.codebook or [])
    quote_texts = [q.text for q in quotes if q.text]

    if len(quote_texts) < 3:
        return []

    payload = json.dumps(
        {
            "quotes": quote_texts[:30],  # cap to avoid token overflow
            "existing_codebook": [
                {"code_id": c["code_id"], "name": c.get("name", ""), "description": c.get("description", "")}
                for c in codebook
            ],
        },
        ensure_ascii=False,
    )

    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": payload},
        ]

        gw_client = None
        try:
            from merism.llm_gateway.client import get_client
            gw_client = await get_client("chat", team=study.team, trace_id=uuid4())
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

        parsed = SuggestionResult.model_validate_json(raw)
    except (LLMUnavailableError, Exception) as exc:
        logger.warning(
            "inductive_code_suggester.llm_failed",
            extra={"error": str(exc), "study_id": str(study.id)},
        )
        return []

    results = [
        {
            "code_id": s.code_id,
            "name": s.name,
            "description": s.description,
            "evidence_quotes": s.evidence_quotes,
            "rationale": s.rationale,
        }
        for s in parsed.suggestions
    ]

    logger.info(
        "inductive_code_suggester.done",
        extra={"study_id": str(study.id), "suggestions": len(results)},
    )
    return results
