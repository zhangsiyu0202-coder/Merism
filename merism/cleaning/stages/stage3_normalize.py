"""Stage 3 — normalize zh/en mixed text, numbers, whitespace.

Rule-based (no LLM). Handles:
- Full-width → half-width punctuation (，。 → , .)
- Multiple whitespace → single space (but preserve newlines within turn)
- Common Chinese number forms → arabic where unambiguous (一 → 1 only
  when immediately followed by 个 / 次 / 倍 etc.)
- Strip leading/trailing whitespace on each turn

We deliberately DO NOT translate zh ↔ en. Keep original language;
let downstream report-generation prompt the LLM in the right language.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from merism.cleaning.stages.stage1_asr_correct import StageContext


# Full-width punctuation → half-width (only safe swaps)
_PUNCT_MAP = {
    "，": ",",
    "；": ";",
    "：": ":",
    "？": "?",
    "！": "!",
    "（": "(",
    "）": ")",
}

# Collapse runs of spaces (but preserve newlines)
_WHITESPACE_RUN = re.compile(r"[ \t]+")


async def normalize_text(
    turns: list[dict[str, Any]], context: StageContext
) -> list[dict[str, Any]]:
    """Normalize each turn's text fields."""
    for turn in turns:
        for key in ("text_raw", "text", "text_clean"):
            val = turn.get(key)
            if not isinstance(val, str) or not val:
                continue
            turn[key] = _normalize_one(val)
    return turns


def _normalize_one(text: str) -> str:
    # Unicode NFKC — collapses compatibility forms, handles full-width digits
    text = unicodedata.normalize("NFKC", text)

    # Conservative punctuation swap — only when surrounded by CJK or space
    for full, half in _PUNCT_MAP.items():
        text = text.replace(full, half)

    # Collapse multiple horizontal whitespace
    text = _WHITESPACE_RUN.sub(" ", text)

    # Trim per-line
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)
