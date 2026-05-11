"""Codebook seeder — Sprint 3 first-run agent.

Derives an initial set of 5-12 codes from a study's
``research_goal`` + ``research_objectives``. Each code is a small
analytical label researchers will attach to quotes; the seeded set is
**not final** — the inductive tagger (``quote_tagger.py``) will
suggest new codes as real quotes arrive, and researchers can manually
edit the codebook through the Settings tab.

Called once per study on the first post-session pipeline run, gated by
``Study.codebook`` being empty. Subsequent runs short-circuit.
"""

from __future__ import annotations

import json
import logging

from asgiref.sync import sync_to_async
from pydantic import BaseModel, ConfigDict, Field

from merism.memai.llm import LLMUnavailableError, default_model, get_llm
from merism.models import Study

logger = logging.getLogger(__name__)


class SeedCode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code_id: str = Field(min_length=1, max_length=64, description="kebab_case slug")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=300)
    examples: list[str] = Field(default_factory=list, max_length=3)


class SeedCodebook(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codes: list[SeedCode] = Field(min_length=3, max_length=15)


SYSTEM_PROMPT = """\
You are a qualitative research methodologist. Given a study's research
goal and objectives, produce an initial codebook of 5-12 analytical
codes that capture the phenomena the researcher wants to detect in
participant quotes.

Rules:
1. One code = one distinct pattern of meaning. Overlapping codes are
   a design smell — combine them.
2. Code names use Title Case (e.g. "Pricing Complaint").
3. ``code_id`` is ``snake_case`` (``pricing_complaint``), matching
   Python identifier rules.
4. Descriptions are one sentence — what does this code catch?
5. Examples are short phrases (not full sentences) that would trigger
   this code when seen in a quote. 1-3 examples per code.
6. Include codes for obvious categories suggested by the objectives
   (e.g. if an objective mentions purchase intent, include a
   ``purchase_intent`` code) AND auxiliary codes that commonly appear
   in conversation (sentiment, confusion, comparison with alternatives).
7. NEVER include codes unrelated to the study's goal. Stay focused.

Output schema: {"codes": [{code_id, name, description, examples}]}.
"""


async def seed_codebook(study: Study) -> list[dict]:
    """Seed ``study.codebook`` if empty. Returns the new codebook (list).

    If the LLM call fails or the study already has codes, returns the
    existing codebook untouched.
    """
    if study.codebook:
        return list(study.codebook)

    goal = (study.research_goal or "").strip()
    objectives: list[str] = list(study.research_objectives or [])
    if not goal and not objectives:
        logger.info(
            "codebook.seeder.skipped_empty_study",
            extra={"study_id": str(study.id)},
        )
        return []

    user_payload = json.dumps(
        {"research_goal": goal, "research_objectives": objectives},
        ensure_ascii=False,
    )

    try:
        client = get_llm(async_=True)
        completion = await client.chat.completions.create(
            model=default_model(),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_payload},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        raw = completion.choices[0].message.content or "{}"
        parsed = SeedCodebook.model_validate_json(raw)
    except (LLMUnavailableError, Exception) as exc:  # noqa: BLE001
        logger.warning(
            "codebook.seeder.llm_failed",
            extra={"error": str(exc), "study_id": str(study.id)},
        )
        return []

    entries = [
        {
            "code_id": c.code_id,
            "name": c.name,
            "description": c.description,
            "examples": c.examples,
            "source": "seeded",
        }
        for c in parsed.codes
    ]

    # Persist on the study row.
    study.codebook = entries
    await _asave_study(study)
    logger.info(
        "codebook.seeder.done",
        extra={"study_id": str(study.id), "code_count": len(entries)},
    )
    return entries


async def _asave_study(study: Study) -> None:
    asave = getattr(study, "asave", None)
    if callable(asave):
        await asave(update_fields=["codebook", "updated_at"])
    else:  # pragma: no cover
        await sync_to_async(study.save)(update_fields=["codebook", "updated_at"])
