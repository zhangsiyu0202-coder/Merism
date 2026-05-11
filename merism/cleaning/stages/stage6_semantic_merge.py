"""Stage 6 — semantic merge of fragmented utterances.

ASR often produces multiple turns that are actually one thought:

    Participant: "So I think..."
    Participant: "Actually no, I mean..."
    Participant: "...the pricing is the main issue."

A naive viewer sees 3 separate turns; Stage 5 (llm_polish) runs each
turn individually so it can't merge. This stage asks the LLM to merge
runs of consecutive same-speaker turns into coherent utterances,
preserving the timestamps of the first + last turn.

Only merges when:
1. Consecutive same-speaker turns
2. Gap between them < 8 seconds (otherwise it's likely a new thought)
3. Combined text < 1000 chars (don't merge whole sessions)

Best-effort: on LLM failure or parse error, return original turns.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from merism.cleaning.stages.stage1_asr_correct import StageContext

logger = logging.getLogger(__name__)


MAX_MERGE_GAP_MS = 8000  # 8s between turns
MAX_MERGED_LENGTH = 1000


class MergedUtterance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: int
    merged_text: str = Field(min_length=1)


class MergeBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    utterances: list[MergedUtterance]


SYSTEM_PROMPT = """You merge fragmented speech into coherent sentences.

You will see groups of consecutive turns from ONE speaker that may form a single thought. For each group, produce ONE merged text that preserves EVERY factual detail. Fix obvious incomplete starts ("So I think..." → drop if abandoned), collapse repeated corrections ("no wait, actually") into the final form.

Rules:
- Never add information not present in the original.
- Never drop a concrete fact, number, name, or opinion.
- If a group is clearly NOT one thought (topic change), preserve as-is by concatenating with ". ".
- Output plain prose — no bullets, no headers.

Output JSON: {"utterances": [{"group_id": 0, "merged_text": "..."}, ...]}"""


async def semantic_merge(
    turns: list[dict[str, Any]], context: StageContext
) -> list[dict[str, Any]]:
    """Merge runs of same-speaker consecutive turns into coherent utterances."""
    if len(turns) < 2:
        return turns

    groups = _group_mergeable_runs(turns)
    if not any(len(g) > 1 for g in groups):
        return turns  # No multi-turn groups — nothing to merge

    # Build LLM request — only send the multi-turn groups
    multi_groups = [(i, g) for i, g in enumerate(groups) if len(g) > 1]
    payload = [
        {
            "group_id": gid,
            "turns": [turns[idx].get("text_clean") or turns[idx].get("text", "") for idx in group],
        }
        for gid, group in multi_groups
    ]

    try:
        merged_by_group = await _invoke_llm(context, payload)
    except Exception:
        logger.exception(
            "cleaning.stage6.merge_failed",
            extra={"session_id": str(context.session_id)},
        )
        return turns

    # Apply merges — build new turn list
    new_turns: list[dict[str, Any]] = []
    for gid, group in enumerate(groups):
        if len(group) == 1:
            new_turns.append(turns[group[0]])
            continue
        merged_text = merged_by_group.get(gid)
        if not merged_text:
            # LLM skipped this group — keep originals
            for idx in group:
                new_turns.append(turns[idx])
            continue
        # Use first turn as the base; update its text + timestamps
        base = dict(turns[group[0]])
        last = turns[group[-1]]
        base["text_clean"] = merged_text
        base["text"] = merged_text
        base["ts_end_ms"] = last.get("ts_end_ms", base.get("ts_end_ms", 0))
        base["merged_from"] = [turns[i].get("id") for i in group if turns[i].get("id")]
        new_turns.append(base)

    logger.info(
        "cleaning.stage6.done: session=%s groups=%d merged=%d",
        str(context.session_id), len(multi_groups),
        sum(1 for gid in range(len(multi_groups)) if merged_by_group.get(multi_groups[gid][0])),
    )
    return new_turns


def _group_mergeable_runs(turns: list[dict[str, Any]]) -> list[list[int]]:
    """Partition turn indices into groups of mergeable runs.

    A "mergeable run" = consecutive same-speaker turns with a gap <
    MAX_MERGE_GAP_MS. Solo turns get their own single-element group.
    """
    groups: list[list[int]] = []
    current: list[int] = []
    for i, turn in enumerate(turns):
        if not current:
            current = [i]
            continue
        prev = turns[current[-1]]
        same_role = turn.get("role") == prev.get("role")
        gap = turn.get("ts_start_ms", 0) - prev.get("ts_end_ms", 0)
        combined_text = sum(
            len((turns[j].get("text_clean") or turns[j].get("text") or "")) for j in current + [i]
        )
        if same_role and gap < MAX_MERGE_GAP_MS and combined_text < MAX_MERGED_LENGTH:
            current.append(i)
        else:
            groups.append(current)
            current = [i]
    if current:
        groups.append(current)
    return groups


async def _invoke_llm(
    context: StageContext, payload: list[dict[str, Any]]
) -> dict[int, str]:
    """Call the LLM and return {group_id: merged_text}."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]

    raw: str | None = None
    # Try gateway first
    try:
        from merism.llm_gateway.client import get_client
        from merism.models import Team

        team = await _get_team(context.team_id)
        if team is not None:
            client = await get_client("chat", team=team, trace_id=context.trace_id or uuid4())
            response = await client.complete(
                messages=messages, response_format={"type": "json_object"}, temperature=0.1,
            )
            raw = response.choices[0].message.content or "{}"
    except Exception:
        raw = None

    if raw is None:
        from merism.memai.llm import default_model, get_llm

        legacy = get_llm(async_=True)
        completion = await legacy.chat.completions.create(
            model=default_model(),
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        raw = completion.choices[0].message.content or "{}"

    parsed = MergeBatch.model_validate_json(raw)
    return {u.group_id: u.merged_text for u in parsed.utterances}


async def _get_team(team_id: Any):
    """Sync-safe team fetch."""
    from asgiref.sync import sync_to_async

    from merism.models import Team

    @sync_to_async
    def _fetch():
        try:
            return Team.objects.get(id=team_id)
        except Team.DoesNotExist:
            return None

    return await _fetch()
