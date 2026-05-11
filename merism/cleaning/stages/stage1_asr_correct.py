"""Stage 1 — ASR correction via glossary lookup.

Applies team/study glossary entries to transcript turns. Fast, rule-based,
no LLM. Variants → canonical, optionally case-insensitive.

Future: nearest-neighbor edit distance matching for unknown variants.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from asgiref.sync import sync_to_async

from merism.models import Glossary

logger = logging.getLogger(__name__)


@dataclass
class StageContext:
    """Per-session context passed to every stage."""

    team_id: Any
    study_id: Any
    session_id: Any
    # Optional LLM gateway trace id
    trace_id: Any | None = None


async def correct_with_glossary(
    turns: list[dict[str, Any]], context: StageContext
) -> list[dict[str, Any]]:
    """Apply glossary replacements in-place to turn texts."""
    entries = await _fetch_glossary(context.team_id, context.study_id)
    if not entries:
        return turns

    # Pre-compile substitution table
    subs: list[tuple[re.Pattern, str]] = []
    for entry in entries:
        canonical = entry["canonical"]
        for variant in entry.get("variants", []):
            if not variant:
                continue
            flags = re.IGNORECASE if entry.get("case_insensitive", True) else 0
            pattern = re.compile(re.escape(variant), flags)
            subs.append((pattern, canonical))

    if not subs:
        return turns

    replaced_count = 0
    for turn in turns:
        for key in ("text_raw", "text", "text_clean"):
            val = turn.get(key)
            if not isinstance(val, str):
                continue
            new_val = val
            for pattern, canonical in subs:
                new_val, n = pattern.subn(canonical, new_val)
                replaced_count += n
            turn[key] = new_val

    if replaced_count:
        logger.info(
            "cleaning.stage1.replaced: session=%s count=%d",
            str(context.session_id), replaced_count,
        )
    return turns


@sync_to_async
def _fetch_glossary(team_id: Any, study_id: Any) -> list[dict[str, Any]]:
    """Fetch study + team-wide glossary entries."""
    from django.db.models import Q

    qs = Glossary.objects.filter(team_id=team_id).filter(
        Q(study_id=study_id) | Q(study_id__isnull=True)
    )
    return [
        {"canonical": g.canonical, "variants": g.variants, "case_insensitive": g.case_insensitive}
        for g in qs
    ]
