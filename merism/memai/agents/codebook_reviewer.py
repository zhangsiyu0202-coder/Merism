"""CodebookReviewer — generates codebook change proposals.

Analyzes the current codebook + accumulated inductive suggestions + usage
patterns and proposes structural changes: merge overlapping codes, deprecate
unused ones, add validated inductive suggestions, rename ambiguous codes,
split overly broad codes.

Inspired by Chen et al. (ACL 2026) merge metrics: Coverage, Overlap,
Novelty, Divergence.

Single LLM call, structured JSON output.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from merism.memai.llm import LLMUnavailableError, default_model, get_llm
from merism.models import Study

logger = logging.getLogger(__name__)


class ChangeProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    change_type: Literal["add", "merge", "split", "rename", "deprecate"]
    payload: dict[str, Any]
    rationale: str = Field(max_length=300)
    confidence: float = Field(ge=0.0, le=1.0)


class ReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposals: list[ChangeProposal] = Field(default_factory=list, max_length=5)


SYSTEM_PROMPT = """\
You are a qualitative research codebook reviewer. Given:
- The current codebook (list of codes with usage counts)
- New inductive suggestions from the latest session

Propose structural changes to improve the codebook. Types of changes:

1. **add**: An inductive suggestion is valid and distinct. Payload:
   {"code": {"code_id": "...", "name": "...", "description": "...", "source": "inductive"}}

2. **merge**: Two or more codes overlap significantly. Payload:
   {"source_ids": ["code_a", "code_b"], "target_id": "code_a", "target_name": "..."}

3. **split**: A code is too broad, covering disparate patterns. Payload:
   {"source_id": "...", "targets": [{"code_id": "...", "name": "...", "description": "..."}]}

4. **rename**: A code name is ambiguous or inconsistent. Payload:
   {"code_id": "...", "old_name": "...", "new_name": "..."}

5. **deprecate**: A code has zero or near-zero usage and is redundant. Payload:
   {"code_id": "...", "replaced_by": "other_code_id" or null}

Rules:
- Maximum 5 proposals per review cycle.
- Only propose changes with confidence >= 0.6.
- Prefer conservative changes (rename > merge > deprecate > split).
- Do NOT propose adding a code that near-duplicates an existing one.
- If the codebook is healthy and suggestions are redundant, return empty list.

Output JSON: {"proposals": [{change_type, payload, rationale, confidence}]}
"""


async def review_codebook(
    study: Study,
    inductive_suggestions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Review codebook and return change proposals."""
    codebook: list[dict[str, Any]] = list(study.codebook or [])
    if not codebook:
        return []

    payload = json.dumps(
        {
            "codebook": codebook,
            "inductive_suggestions": inductive_suggestions,
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

        parsed = ReviewResult.model_validate_json(raw)
    except (LLMUnavailableError, Exception) as exc:
        logger.warning(
            "codebook_reviewer.llm_failed",
            extra={"error": str(exc), "study_id": str(study.id)},
        )
        return []

    # Filter by confidence threshold
    results = [
        {
            "change_type": p.change_type,
            "payload": p.payload,
            "rationale": p.rationale,
            "confidence": p.confidence,
        }
        for p in parsed.proposals
        if p.confidence >= 0.6
    ]

    logger.info(
        "codebook_reviewer.done",
        extra={"study_id": str(study.id), "proposals": len(results)},
    )
    return results
