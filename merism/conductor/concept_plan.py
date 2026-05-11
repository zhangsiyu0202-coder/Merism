"""Concept-rotation guide expansion.

Turns a raw guide (with ``scope=per_concept`` sections) into a
flattened guide that the moderator traverses linearly, injecting
concept context into every question that belongs to an expanded
section.

The moderator's cursor / prompt code doesn't need to know about
concept blocks — it just reads questions in order.

Call :func:`expand_guide` at session init, persist the result on
``ExecutionState.expanded_sections`` + ``concept_by_question_id``.
"""

from __future__ import annotations

from typing import Any

from merism.concept import compute_order


def expand_guide(
    raw_sections: list[dict[str, Any]],
    blocks: dict[str, dict[str, Any]],
    session_seed: str,
    block_seed_override: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Expand per_concept sections + emit concept metadata map.

    Parameters
    ----------
    raw_sections
        The guide as stored: list of section dicts each with ``id``,
        ``title``, ``scope``, optional ``concept_block_id``,
        ``questions``.
    blocks
        ``{block_id: {"title": str, "rotation": str, "concepts":
        [{"id": str, "stimulus_id": str, "label": str, "notes": str,
        "rank": int}, ...]}}``.
    session_seed
        Default rotation seed; used when no per-block override is
        provided. Usually the session id.
    block_seed_override
        ``{block_id: str}`` per-block seed override. Callers use this
        to feed the persistent :class:`ConceptRotationCursor` position
        into ``latin_square`` blocks while letting ``random`` blocks
        keep the session seed.

    Returns
    -------
    (expanded_sections, concept_by_question_id)
    """
    expanded: list[dict[str, Any]] = []
    concept_by_qid: dict[str, dict[str, Any]] = {}
    overrides = block_seed_override or {}

    for section in raw_sections:
        scope = section.get("scope", "global")

        if scope != "per_concept":
            # Keep as-is. Mark its questions as having no concept context.
            expanded.append(section)
            for q in section.get("questions", []) or []:
                qid = q.get("id")
                if qid:
                    concept_by_qid[qid] = _global_marker(scope)
            continue

        block_id = section.get("concept_block_id")
        if not block_id or block_id not in blocks:
            # Misconfigured: skip expansion, treat as global.
            expanded.append(section)
            for q in section.get("questions", []) or []:
                qid = q.get("id")
                if qid:
                    concept_by_qid[qid] = _global_marker("global")
            continue

        block = blocks[block_id]
        concepts = block.get("concepts", []) or []
        concept_ids = [c["id"] for c in concepts]
        if not concept_ids:
            expanded.append(section)
            continue

        order = compute_order(block.get("rotation", "random_per_session"), concept_ids, overrides.get(block_id, session_seed))
        concept_lookup = {c["id"]: c for c in concepts}
        total = len(order)

        for idx, concept_id in enumerate(order):
            concept = concept_lookup[concept_id]
            expanded_section = {
                "id": f"{section['id']}__c{idx}",
                "title": f"{section.get('title', '')} · {idx + 1}/{total}",
                "scope": "per_concept",
                "concept_block_id": block_id,
                "concept_id": concept_id,
                "concept_index": idx,
                "concept_count": total,
                "questions": [],
            }
            for q in section.get("questions", []) or []:
                orig_qid = q.get("id", "")
                new_qid = f"{orig_qid}__c{idx}"
                expanded_q = {**q, "id": new_qid, "original_question_id": orig_qid}
                expanded_section["questions"].append(expanded_q)
                concept_by_qid[new_qid] = {
                    "concept_id": concept_id,
                    "concept_index": idx,
                    "concept_count": total,
                    "block_id": block_id,
                    "block_title": block.get("title", ""),
                    "stimulus_id": concept.get("stimulus_id"),
                    "label": concept.get("label", ""),
                    "notes": concept.get("notes", ""),
                }
            expanded.append(expanded_section)

    return expanded, concept_by_qid


def _global_marker(scope: str) -> dict[str, Any]:
    return {
        "concept_id": None,
        "concept_index": None,
        "concept_count": None,
        "block_id": None,
        "block_title": None,
        "stimulus_id": None,
        "label": "",
        "notes": "",
        "scope": scope,
    }


def concept_transition_payload(
    concept_by_qid: dict[str, dict[str, Any]],
    old_qid: str,
    new_qid: str,
    stimulus_lookup: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Return a stimulus_show payload if the cursor just moved to a NEW concept.

    Emits ``None`` when:
    - the new question has no concept (global/comparative/unknown);
    - the new concept is the same as the old concept (mid-concept turn);
    - the new concept has no associated stimulus.

    ``stimulus_lookup`` maps ``stimulus_id → {"kind": str, "content": dict}``
    so the caller can populate the wire message. If omitted, ``kind`` /
    ``content`` default to placeholders (caller is responsible for
    hydrating from DB before emitting the frame).
    """
    new_info = concept_by_qid.get(new_qid)
    if not new_info or new_info.get("concept_id") is None:
        return None

    old_info = concept_by_qid.get(old_qid) or {}
    if old_info.get("concept_id") == new_info["concept_id"]:
        return None

    stim_id = new_info.get("stimulus_id")
    if not stim_id:
        return None

    stim = (stimulus_lookup or {}).get(stim_id, {})

    return {
        "stimulus_id": stim_id,
        "kind": stim.get("kind", "image"),
        "content": stim.get("content", {}),
        "concept_index": new_info.get("concept_index"),
        "concept_count": new_info.get("concept_count"),
        "block_title": new_info.get("block_title"),
    }
