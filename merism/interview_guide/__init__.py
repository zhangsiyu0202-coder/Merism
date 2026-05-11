"""Validation for :class:`InterviewGuide.sections` JSON.

Schema (one section)::

    {
        "id": "warmup",                 # required, str
        "title": "热身",                 # required, str
        "scope": "global",              # required, "global" | "per_concept" | "comparative"
        "concept_block_id": "...",      # required when scope == "per_concept"
        "questions": [
            {
                "id": "q1",
                "text": "...",
                "intent": "...",              # optional, str — NN/g + Qualz.ai
                "probe_policy": "light",      # none | light | deep — default light
                "max_probes": 3,              # 1..5 — default 3
                "linked_stimulus_ids": [...], # optional
                "required": true,             # optional
            },
            ...
        ]
    }

``scope`` semantics (Concept Testing 2.0):
    - ``global`` — section runs once per session (warmup, closing).
    - ``per_concept`` — section runs once per concept in the named
      block, with ``{{concept}}`` substitution in prompts.
    - ``comparative`` — section runs once after all concepts, meant
      for A/B/C comparison questions.

Back-compat: legacy questions carrying ``followup_depth: int`` +
``probe_directions: list[str]`` are accepted and mapped to the new
fields (see :func:`_normalize_question`).
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers


VALID_SCOPES = {"global", "per_concept", "comparative"}
VALID_PROBE_POLICIES = {"none", "light", "deep"}
DEFAULT_PROBE_POLICY = "light"
DEFAULT_MAX_PROBES = 3
MIN_MAX_PROBES = 1
MAX_MAX_PROBES = 5


def validate_sections(sections: Any) -> list[dict[str, Any]]:
    if not isinstance(sections, list):
        raise serializers.ValidationError("sections must be a list")

    out: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for idx, section in enumerate(sections):
        if not isinstance(section, dict):
            raise serializers.ValidationError(f"sections[{idx}] must be an object")

        section_id = section.get("id")
        if not isinstance(section_id, str) or not section_id:
            raise serializers.ValidationError(f"sections[{idx}].id must be a non-empty string")
        if section_id in seen_ids:
            raise serializers.ValidationError(f"duplicate section id '{section_id}'")
        seen_ids.add(section_id)

        title = section.get("title", "")
        if not isinstance(title, str):
            raise serializers.ValidationError(f"sections[{idx}].title must be a string")

        scope = section.get("scope", "global")
        if scope not in VALID_SCOPES:
            raise serializers.ValidationError(
                f"sections[{idx}].scope must be one of {sorted(VALID_SCOPES)}, got {scope!r}"
            )

        concept_block_id = section.get("concept_block_id")
        if scope == "per_concept" and not concept_block_id:
            raise serializers.ValidationError(
                f"sections[{idx}] has scope=per_concept; concept_block_id is required"
            )

        raw_questions = section.get("questions", [])
        if not isinstance(raw_questions, list):
            raise serializers.ValidationError(f"sections[{idx}].questions must be a list")

        questions: list[dict[str, Any]] = []
        for q_idx, raw_q in enumerate(raw_questions):
            questions.append(_normalize_question(raw_q, section_idx=idx, q_idx=q_idx))

        out.append(
            {
                "id": section_id,
                "title": title,
                "scope": scope,
                "concept_block_id": concept_block_id if scope == "per_concept" else None,
                "questions": questions,
            }
        )

    return out


def _normalize_question(
    raw: Any, *, section_idx: int, q_idx: int
) -> dict[str, Any]:
    """Validate + normalise one question into the current schema.

    Back-compat:
        - ``followup_depth: int``      → ``max_probes`` (clamped to 1..5)
                                       + ``probe_policy`` derived (0=none,
                                       1-2=light, 3+=deep).
        - ``probe_directions: list``   → joined into ``intent`` when the
                                       caller supplied none.
    """
    where = f"sections[{section_idx}].questions[{q_idx}]"
    if not isinstance(raw, dict):
        raise serializers.ValidationError(f"{where} must be an object")

    q_id = raw.get("id")
    if not isinstance(q_id, str) or not q_id:
        raise serializers.ValidationError(f"{where}.id must be a non-empty string")

    text = raw.get("text", "")
    if not isinstance(text, str):
        raise serializers.ValidationError(f"{where}.text must be a string")

    intent = raw.get("intent")
    if intent is not None and not isinstance(intent, str):
        raise serializers.ValidationError(f"{where}.intent must be a string if set")

    probe_policy = raw.get("probe_policy", DEFAULT_PROBE_POLICY)
    if probe_policy not in VALID_PROBE_POLICIES:
        raise serializers.ValidationError(
            f"{where}.probe_policy must be one of "
            f"{sorted(VALID_PROBE_POLICIES)}, got {probe_policy!r}"
        )

    max_probes = raw.get("max_probes", DEFAULT_MAX_PROBES)
    # Legacy mapping: prefer explicit max_probes; else derive from followup_depth.
    if "max_probes" not in raw and "followup_depth" in raw:
        legacy = raw["followup_depth"]
        if isinstance(legacy, int):
            max_probes = max(MIN_MAX_PROBES, min(legacy or DEFAULT_MAX_PROBES, MAX_MAX_PROBES))
            if "probe_policy" not in raw:
                probe_policy = "none" if legacy == 0 else ("light" if legacy <= 2 else "deep")

    if not isinstance(max_probes, int):
        raise serializers.ValidationError(f"{where}.max_probes must be an int")
    if not (MIN_MAX_PROBES <= max_probes <= MAX_MAX_PROBES):
        raise serializers.ValidationError(
            f"{where}.max_probes must be in [{MIN_MAX_PROBES}, {MAX_MAX_PROBES}]"
        )

    # Back-compat: fold ``probe_directions`` into intent when missing.
    if not intent and isinstance(raw.get("probe_directions"), list):
        directions = [d for d in raw["probe_directions"] if isinstance(d, str) and d.strip()]
        if directions:
            intent = "Probe around: " + "; ".join(directions)

    linked_stimulus_ids = raw.get("linked_stimulus_ids", [])
    if not isinstance(linked_stimulus_ids, list):
        raise serializers.ValidationError(
            f"{where}.linked_stimulus_ids must be a list"
        )
    linked_stimulus_ids = [
        str(s) for s in linked_stimulus_ids if isinstance(s, (str, int))
    ]

    required = bool(raw.get("required", False))

    # Preserve ``original_question_id`` when concept_plan expanded us.
    normalised: dict[str, Any] = {
        "id": q_id,
        "text": text,
        "intent": intent or "",
        "probe_policy": probe_policy,
        "max_probes": max_probes,
        "linked_stimulus_ids": linked_stimulus_ids,
        "required": required,
    }
    if "original_question_id" in raw:
        normalised["original_question_id"] = raw["original_question_id"]
    # Keep the legacy field on the wire so old clients don't crash; new
    # clients should ignore it. TODO: drop in R15.
    normalised["followup_depth"] = max_probes
    return normalised
