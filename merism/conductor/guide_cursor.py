"""Interview guide traversal.

Pure functions operating on the ``sections`` JSON a :class:`InterviewGuide`
stores. No ORM, no side effects — easy to unit-test.

A guide section has this shape::

    {
        "id": "s1",
        "title": "Warmup",
        "questions": [
            {
                "id": "q1",
                "text": "Tell me about your role.",
                "followup_depth": 2,
                "required": True,
                "probe_directions": ["specific examples", "friction"],
                "linked_stimulus_ids": [],
            },
            ...
        ],
    }
"""

from __future__ import annotations

from typing import Any


def find_question(
    sections: list[dict[str, Any]], question_id: str
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Locate a question by id; return ``(section, question)`` or ``(None, None)``."""
    for section in sections:
        for question in section.get("questions", []):
            if question.get("id") == question_id:
                return section, question
    return None, None


def next_question(
    sections: list[dict[str, Any]],
    current_question_id: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return the question immediately following ``current_question_id``.

    Crosses section boundaries. If ``current_question_id`` is empty, returns
    the first question in the first section (the opening question).
    Returns ``(None, None)`` at end of guide.
    """
    if not current_question_id:
        if not sections:
            return None, None
        first_section = sections[0]
        questions = first_section.get("questions", [])
        if not questions:
            return None, None
        return first_section, questions[0]

    found = False
    for section in sections:
        questions = section.get("questions", [])
        for question in questions:
            if found:
                return section, question
            if question.get("id") == current_question_id:
                found = True
    return None, None


def followup_budget(guide_sections: list[dict[str, Any]], question_id: str) -> int:
    """Return the per-question probe budget (0 if not found).

    Prefers the new ``max_probes`` field; falls back to legacy
    ``followup_depth`` so pre-Sprint-1 seeds keep working.
    """
    _, question = find_question(guide_sections, question_id)
    if question is None:
        return 0
    if "max_probes" in question:
        return int(question.get("max_probes") or 0)
    return int(question.get("followup_depth", 0))


def is_closing_question(
    sections: list[dict[str, Any]], question_id: str
) -> bool:
    """True if the question lives in the last section (closing)."""
    if not sections:
        return False
    section, _ = find_question(sections, question_id)
    if section is None:
        return False
    return section.get("id") == sections[-1].get("id")


def first_question(
    sections: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    return next_question(sections, current_question_id="")


def dynamic_probe_config(
    guide_sections: list[dict[str, Any]], question_id: str
) -> dict[str, Any]:
    """Return the dynamic_probe config for a question, or disabled default."""
    _, question = find_question(guide_sections, question_id)
    if question is None:
        return {"enabled": False, "max_extra_rounds": 0, "triggers": []}
    dp = question.get("dynamic_probe")
    if not dp or not isinstance(dp, dict):
        return {"enabled": False, "max_extra_rounds": 0, "triggers": []}
    return {
        "enabled": bool(dp.get("enabled", False)),
        "max_extra_rounds": int(dp.get("max_extra_rounds", 0)),
        "triggers": list(dp.get("triggers", [])),
    }
