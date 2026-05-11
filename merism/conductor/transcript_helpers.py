"""Transcript reading helpers — the single point of truth for "give me
the right text from this turn".

Sprint 2 introduced a dual-text shape for interview turns:

    {
        "ts": 1234567890.0,
        "role": "agent" | "participant",
        "text_raw":   "嗯嗯，我觉得挺好的",  # original ASR
        "text_clean": "我觉得挺好的",         # intelligent verbatim
        "text":       "我觉得挺好的",          # legacy mirror of clean
        "question_id": "...",
        "concept_id":  "...",
    }

Legacy sessions (pre-Sprint-2) carry only ``text``. This module hides
the fallback logic from every downstream consumer (Ask Merism, analysis
agents, exports).
"""

from __future__ import annotations

from typing import Any, Literal

TurnTextMode = Literal["clean", "raw"]


def get_turn_text(turn: dict[str, Any], mode: TurnTextMode = "clean") -> str:
    """Return the requested text for a single turn.

    Priority order:
        mode="clean": text_clean → text → text_raw → ""
        mode="raw":   text_raw   → text → text_clean → ""

    Never raises. Empty strings are returned when the turn has no text
    at all — downstream code should treat that as a no-op.
    """
    if mode == "raw":
        for key in ("text_raw", "text", "text_clean"):
            value = turn.get(key)
            if value:
                return str(value)
        return ""
    # clean (default)
    for key in ("text_clean", "text", "text_raw"):
        value = turn.get(key)
        if value:
            return str(value)
    return ""


def get_transcript_text(
    transcript: list[dict[str, Any]],
    *,
    mode: TurnTextMode = "clean",
    include_roles: tuple[str, ...] = ("participant", "agent"),
    separator: str = "\n",
) -> str:
    """Flatten a transcript into plain text using :func:`get_turn_text`.

    ``include_roles`` filters which turns end up in the output — default
    is both participant and agent. ``separator`` joins the turns; the
    default newline produces a simple readable log.
    """
    parts: list[str] = []
    for turn in transcript or []:
        if turn.get("role") not in include_roles:
            continue
        text = get_turn_text(turn, mode)
        if text:
            role = turn.get("role", "")
            parts.append(f"[{role}] {text}")
    return separator.join(parts)


def has_clean_transcript(transcript: list[dict[str, Any]]) -> bool:
    """True when every participant + agent turn has a non-empty ``text_clean``.

    Used by :mod:`merism.conductor.tasks` to decide whether a session
    has already been processed — idempotency guard.
    """
    if not transcript:
        return False
    for turn in transcript:
        if turn.get("role") not in {"agent", "participant"}:
            continue
        if not turn.get("text_clean"):
            return False
    return True
