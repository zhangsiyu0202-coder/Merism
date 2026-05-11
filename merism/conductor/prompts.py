"""Interview moderator system-prompt builder.

Per Sprint 1: the system prompt now carries an explicit, structured
``CURRENT QUESTION STATE`` block so the LLM gets its decision inputs
as fields (not prose). Four ``DECISION RULES`` translate the
researcher's ``probe_policy`` + ``max_probes`` into hard constraints
the model must follow. The server-side ``decision_validator`` enforces
the same rules regardless of what the LLM returns — so the config
*will* be respected even if the model hallucinates.

ModeratorDecision now also carries probe metadata (``probe_type`` /
``probe_triggered_by`` / ``matches_rule``) so researchers can audit
why the AI probed, and so analysis can bucket probes by the four
NN/g types (expansion / clarification / feeling / reasoning).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ModeratorDecision(BaseModel):
    """The function-call output the moderator returns alongside text.

    PRODUCT.md §5.2: **one LLM call** decides both "what to say" and
    "what to do next". Do not split this into separate calls.
    """

    model_config = ConfigDict(extra="forbid")

    next_action: Literal["followup", "move_on", "clarify", "close"]
    next_question_id: str | None = Field(
        default=None,
        description="Required when next_action == 'move_on'; ignored otherwise.",
    )
    # ── Sprint 1 additions: audit trail for probes ────────────────
    probe_type: Literal["expansion", "clarification", "feeling", "reasoning"] | None = (
        Field(
            default=None,
            description=(
                "NN/g's 4 probe types. Required when next_action == 'followup'; "
                "must be null otherwise."
            ),
        )
    )
    probe_triggered_by: str | None = Field(
        default=None,
        description=(
            "Human-readable trigger (\"answer was vague\", \"mentioned cost\"). "
            "Required when next_action == 'followup'."
        ),
    )
    matches_rule: int | None = Field(
        default=None,
        ge=1,
        le=4,
        description=(
            "Which DECISION RULE (1-4) the model claims it followed. "
            "Used only for telemetry; the server-side validator enforces "
            "rules regardless."
        ),
    )


# Probe policy → copy used in the DECISION RULES block.
_POLICY_CLAUSE = {
    "none": (
        "The researcher has set probe_policy=none for this question. "
        "You MUST NOT ask a follow-up. Emit move_on after the participant replies."
    ),
    "light": (
        "The researcher has set probe_policy=light. Probe only when the "
        "answer is vague, too short, or internally contradictory. A detailed "
        "initial reply is a valid stopping point — emit move_on."
    ),
    "deep": (
        "The researcher has set probe_policy=deep — this is a core question. "
        "You MUST probe at least once. Even if the initial answer seems complete, "
        "ask one follow-up that sharpens the intent below before moving on."
    ),
}


SYSTEM_PROMPT_TEMPLATE = """\
You are an interviewer hosting a qualitative research session with a participant.
Your one and only goal is to gather honest, specific answers that serve the
research_goal below. You are concise, warm, and never leading.

<research_goal>
{research_goal}
</research_goal>

<current_question_state>
id:             {question_id}
text:           {question_text}
intent:         {intent}
probe_policy:   {probe_policy}
probes_done:    {probes_done}
max_probes:     {max_probes}
remaining:      {remaining}
</current_question_state>

<current_stimulus>
{current_stimulus}
</current_stimulus>

<concept_context>
{concept_context}
</concept_context>

<vision_context>
{vision_context}
</vision_context>

DECISION RULES (non-negotiable — the server enforces these):
1. {policy_clause}
2. If probes_done >= max_probes, you MUST emit move_on. Never exceed the cap.
3. If you emit next_action=followup, set probe_type to one of:
     - expansion      ("Can you expand on that?", when reply is short)
     - clarification  ("What do you mean by X?", when a term is unclear)
     - feeling        ("How did you feel?", when probing emotion)
     - reasoning      ("Why do you think that?", when probing motivation)
   and set probe_triggered_by to a short human-readable reason.
4. If you emit next_action=move_on, set next_question_id to the next
   question's id (use ANY question ID from the guide, not just the next
   sequential — but prefer sequential unless researcher intent dictates
   otherwise). probe_type and probe_triggered_by must be null.

CONVERSATIONAL RULES:
- Speak ONLY in natural spoken language — no markdown, no bullet points,
  no numbered lists in your audible reply.
- Keep replies short (one or two sentences). Probes are shorter than setups.
- If the participant goes off-topic, gently bring them back to the current
  question intent (one sentence; do not scold).
- When concept_context is non-empty, the participant sees a number (e.g.
  "Concept 2 of 3") but NEVER the internal label. Do not say "Concept A".

Return format: stream the spoken reply first, then emit ONE function call
matching the ModeratorDecision schema exactly.
"""


def build_system_prompt(
    *,
    research_goal: str,
    question_id: str = "",
    question_text: str = "",
    intent: str = "",
    probe_policy: str = "light",
    probes_done: int = 0,
    max_probes: int = 3,
    current_stimulus: str = "",
    vision_context: str = "",
    concept_context: str = "",
    # legacy kwargs retained for callers that haven't been updated yet —
    # these are derivable from the new ones and will be removed in R15.
    current_question: str | None = None,
    remaining_followups: int | None = None,
) -> str:
    """Build the moderator system prompt with the per-turn state injected."""
    # Legacy compat: callers that still pass ``current_question`` get it
    # mapped to ``question_text`` so we can merge this without touching
    # every call site at once.
    if current_question is not None and not question_text:
        question_text = current_question

    remaining = (
        remaining_followups
        if remaining_followups is not None
        else max(0, max_probes - probes_done)
    )
    policy_clause = _POLICY_CLAUSE.get(probe_policy, _POLICY_CLAUSE["light"])

    return SYSTEM_PROMPT_TEMPLATE.format(
        research_goal=research_goal.strip(),
        question_id=question_id or "(unset)",
        question_text=(question_text or "").strip() or "(empty)",
        intent=(intent or "").strip() or "(not specified)",
        probe_policy=probe_policy,
        probes_done=probes_done,
        max_probes=max_probes,
        remaining=remaining,
        current_stimulus=current_stimulus.strip() or "(none)",
        concept_context=concept_context.strip() or "(none)",
        vision_context=vision_context.strip() or "(none)",
        policy_clause=policy_clause,
    )


def format_concept_context(concept_info: dict | None) -> str:
    """Render the concept block of the prompt for a per_concept question."""
    if not concept_info or concept_info.get("concept_index") is None:
        return ""
    idx = concept_info["concept_index"]
    count = concept_info["concept_count"]
    block_title = concept_info.get("block_title", "")
    label = concept_info.get("label", "")
    notes = concept_info.get("notes", "")
    parts = [
        f"You are now discussing concept {idx + 1} of {count}"
        + (f" in block '{block_title}'" if block_title else "")
        + ".",
    ]
    if label:
        parts.append(f"Internal label (never mentioned aloud): {label}.")
    if notes:
        parts.append(f"Research brief for this concept: {notes}")
    return "\n".join(parts)


def current_question_state(
    question: dict[str, Any] | None,
    *,
    probes_done: int,
) -> dict[str, Any]:
    """Project a validated question dict into the kwargs ``build_system_prompt``
    expects. Centralises the mapping so the moderator doesn't duplicate it.
    """
    if question is None:
        return {
            "question_id": "",
            "question_text": "",
            "intent": "",
            "probe_policy": "light",
            "probes_done": 0,
            "max_probes": 0,
        }
    return {
        "question_id": question.get("id", ""),
        "question_text": question.get("text", ""),
        "intent": question.get("intent", ""),
        "probe_policy": question.get("probe_policy", "light"),
        "probes_done": probes_done,
        "max_probes": int(question.get("max_probes", question.get("followup_depth", 3))),
    }
