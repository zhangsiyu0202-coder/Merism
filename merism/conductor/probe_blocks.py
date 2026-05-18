"""Probe block schema and utilities.

A probe_block is a structured probing strategy attached to a question
in an InterviewGuide section. It replaces the old `probe_directions: string[]`.

Schema:
    {
        "id": "pb_xxx",
        "type": "example" | "emotion" | "comparison" | "quantify" | "hypothetical" | "custom",
        "prompt": "能举个具体的例子吗？",
        "trigger": "always" | "vague" | "shallow" | "factual_only" | "conditional",
        "condition": null | str,  # only when trigger=conditional
        "max_rounds": 2,
        "priority": 1,
    }
"""

from __future__ import annotations

from typing import TypedDict

PROBE_TYPES = ("example", "emotion", "comparison", "quantify", "hypothetical", "custom")
TRIGGER_TYPES = ("always", "vague", "shallow", "factual_only", "conditional")


class ProbeBlock(TypedDict, total=False):
    id: str
    type: str       # one of PROBE_TYPES
    prompt: str     # suggested probe text
    trigger: str    # one of TRIGGER_TYPES
    condition: str | None
    max_rounds: int
    priority: int


def directions_to_blocks(directions: list[str]) -> list[dict]:
    """Migrate old probe_directions list to probe_blocks."""
    return [
        {
            "id": f"pb_{i}",
            "type": "custom",
            "prompt": d,
            "trigger": "always",
            "max_rounds": 2,
            "priority": i + 1,
        }
        for i, d in enumerate(directions)
    ]


def format_blocks_for_prompt(blocks: list[dict] | None) -> str:
    """Format probe_blocks into a string for LLM prompts."""
    if not blocks:
        return "(none — use your judgment)"
    lines = []
    for b in sorted(blocks, key=lambda x: x.get("priority", 99)):
        trigger = b.get("trigger", "always")
        max_r = b.get("max_rounds", 2)
        lines.append(f"[{b.get('type','custom')}|trigger={trigger}|max={max_r}] {b.get('prompt','')}")
    return "\n".join(lines)
