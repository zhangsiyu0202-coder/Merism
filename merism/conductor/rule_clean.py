"""Rule-based transcript cleaner — fast regex pass before LLM polish.

This module handles the **unambiguous** cases: fillers, repeated stutters,
false starts, long pauses. Anything ambiguous (grammar, coherence, ASR
errors) is left for :mod:`merism.conductor.llm_polish`.

Language support:
    - Chinese Mandarin: 嗯 / 啊 / 呃 / 就是 / 然后 / 那个 / 对对对
    - English: um / uh / er / like / you know / sort of

The regexes are deliberately conservative — they only fire on clear
filler patterns, never on content words. A word like "like" at sentence
boundary with ``like,`` or ``, like,`` is filler; ``I like it`` is not.
"""

from __future__ import annotations

import re


# ── Chinese fillers ─────────────────────────────────────────────
# Standalone filler characters / particles (stand-alone, not part of a
# real word). We match only when they appear as complete tokens between
# spaces, punctuation, or string boundaries — so "嗯" alone or "嗯，"
# triggers, but "嗯嗯嗯" (collapsed below) and "嗯心" wouldn't.
_ZH_FILLER_TOKENS = [
    "嗯",
    "啊",
    "呃",
    "哎",
    "哦",
    "唉",
    "哼",
    "诶",
]

# Phrases that are almost always filler in conversational Mandarin.
# "那个" is the trickiest — it's a demonstrative too; we only strip
# when it's obviously a stall (flanked by commas / pauses).
_ZH_FILLER_PHRASES = [
    r"就是说",
    r"就是呢?",
    r"然后呢?",
    r"对对对+",
    r"是的是的",
    r"那个那个",
]

# ── English fillers ─────────────────────────────────────────────
_EN_FILLER_WORDS = [
    "um",
    "uh",
    "uhh",
    "er",
    "erm",
    "hmm",
    "mmm",
]

# Bracket patterns — "um," "(um)" "[uh]" etc.
_EN_FILLER_PHRASES = [
    r"\bsort of\b",
    r"\bkind of\b,",
    r"\byou know\b,",
    r"\bi mean\b,",
    r"\blike\b(?=,)",  # "like," as a filler
]


# ── False start pattern: word repeated immediately with comma/pause ──
# Matches "I, I went" → "I went" · "我 我 去了" → "我 去了"
_FALSE_START = re.compile(
    r"\b(\w+)\b[\s,、]+(\1\b)",
    flags=re.IGNORECASE,
)

# ── Repeated filler character: "嗯嗯嗯嗯" → (removed) ─────────
_REPEATED_ZH_FILLER = re.compile(
    "([" + "".join(_ZH_FILLER_TOKENS) + "])\\1+",
)

# ── Multiple spaces / trailing comma after filler removal ────────
_MULTI_SPACE = re.compile(r"\s{2,}")
_LEADING_PUNCT = re.compile(r"^[,，、\s]+")
_TRAILING_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.。，、？！?!])")
# Consecutive commas collapse to one: "It's,, really" → "It's, really"
_DOUBLE_COMMA = re.compile(r"([,，])\s*[,，]+")
# Comma directly before a sentence terminator: "第一条，。" → "第一条。"
_COMMA_BEFORE_TERMINATOR = re.compile(r"[,，]\s*(?=[。.!！?？])")
# Trailing comma before end of string: "hello," → "hello"
_TRAILING_COMMA = re.compile(r"[,，]\s*$")


def rule_clean(text: str) -> str:
    """Strip obvious fillers and false starts. Idempotent.

    Conservative: when in doubt, leaves text unchanged. Never drops
    content words. Returns empty string only if the input was all
    fillers.
    """
    if not text or not text.strip():
        return ""

    cleaned = text

    # 1. Collapse repeated filler chars: "嗯嗯嗯嗯" → "嗯"
    cleaned = _REPEATED_ZH_FILLER.sub(r"\1", cleaned)

    # 2. Remove standalone Chinese filler tokens
    for token in _ZH_FILLER_TOKENS:
        # Token flanked by string start / punctuation / space
        pattern = rf"(^|[\s,，、。.!！?？])({token})([\s,，、。.!！?？]|$)"
        cleaned = re.sub(pattern, r"\1\3", cleaned)

    # 3. Remove Chinese filler phrases
    for phrase in _ZH_FILLER_PHRASES:
        cleaned = re.sub(phrase, "", cleaned)

    # 4. Remove English filler words (case-insensitive, word-boundary)
    for word in _EN_FILLER_WORDS:
        pattern = rf"\b{word}\b[,\s]*"
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    # 5. Remove English filler phrases
    for pattern in _EN_FILLER_PHRASES:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    # 6. Collapse false starts
    # Run until stable (e.g. "I, I, I went" needs two passes)
    for _ in range(3):
        new_cleaned = _FALSE_START.sub(r"\1", cleaned)
        if new_cleaned == cleaned:
            break
        cleaned = new_cleaned

    # 7. Normalise whitespace + punctuation
    cleaned = _MULTI_SPACE.sub(" ", cleaned)
    cleaned = _DOUBLE_COMMA.sub(r"\1", cleaned)
    cleaned = _COMMA_BEFORE_TERMINATOR.sub("", cleaned)
    cleaned = _LEADING_PUNCT.sub("", cleaned)
    cleaned = _TRAILING_SPACE_BEFORE_PUNCT.sub(r"\1", cleaned)
    cleaned = _TRAILING_COMMA.sub("", cleaned)

    return cleaned.strip()


def is_mostly_fillers(raw: str, cleaned: str, threshold: float = 0.5) -> bool:
    """Heuristic: returns True if ``cleaned`` dropped > ``threshold`` of
    the original length. Used by orchestrator to decide whether to skip
    an LLM polish pass for a turn that's now almost empty.
    """
    if not raw:
        return False
    ratio_dropped = (len(raw) - len(cleaned)) / len(raw)
    return ratio_dropped > threshold
