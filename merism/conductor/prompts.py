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
    # ── Dual-layer probe fields (Typebot-inspired) ────────────────
    probe_kind: Literal["preset", "dynamic"] | None = Field(
        default=None,
        description=(
            "'preset' — follows researcher's probe_directions, counts against max_probes. "
            "'dynamic' — AI detected unexpected insight, counts against dynamic_probe.max_extra_rounds. "
            "Required when next_action == 'followup'; null otherwise."
        ),
    )
    dynamic_trigger: Literal[
        "new_theme", "contradiction", "strong_emotion", "surprise_finding"
    ] | None = Field(
        default=None,
        description=(
            "Which signal triggered the dynamic probe. Required when probe_kind == 'dynamic'; "
            "must be in the question's dynamic_probe.triggers list."
        ),
    )
    matches_rule: int | None = Field(
        default=None,
        ge=1,
        le=3,
        description=(
            "Which DECISION RULE (1-3) the model claims it followed. "
            "Used only for telemetry; the server-side validator enforces "
            "rules regardless."
        ),
    )

    # ── Phase 3 additions: think-then-act reasoning ──────────────
    think_notes: str | None = Field(
        default=None,
        max_length=500,
        description=(
            "Internal reasoning (not spoken). 1-2 sentences. "
            "What did the participant's answer reveal? Which goal does it "
            "advance? Why this next action? Used for audit + telemetry."
        ),
    )
    target_goal_id: str | None = Field(
        default=None,
        description=(
            "If the moderator is deliberately steering toward a specific "
            "StudyGoal (from coverage_context), the goal's id. Used to "
            "track which follow-ups were coverage-driven."
        ),
    )

    # ── coverage_steer outputs (used by generate step) ────────
    off_topic: bool = Field(
        default=False,
        description=(
            "True if the participant's last message is off-topic from the "
            "current question / research goal. The generate_node uses this "
            "to produce a redirect rather than a substantive reply."
        ),
    )
    steering_strategy: str | None = Field(
        default=None,
        description=(
            "'deepen_current' | 'redirect_to_goal' | 'advance' | 'close_now'. "
            "Tells generate_node how to phrase the reply."
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
你是一位访谈主持人，正在与一位研究参与者进行定性研究访谈。
你唯一的目标是收集诚实、具体的回答，以服务于下方的研究目标。
你简洁、温暖，从不引导。

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

<coverage_context>
{coverage_context}
</coverage_context>

DECISION RULES (non-negotiable — the server enforces these):
1. {policy_clause}
2. If probes_done >= max_probes, you MUST emit move_on. Never exceed the cap.
3. If you emit next_action=followup, set probe_type to one of:
     - expansion      ("能展开说说吗？", when reply is short)
     - clarification  ("你说的X是什么意思？", when a term is unclear)
     - feeling        ("当时你的感受是？", when probing emotion)
     - reasoning      ("你觉得为什么会这样？", when probing motivation)
   and set probe_triggered_by to a short human-readable reason.
4. If you emit next_action=move_on, set next_question_id to the next
   question's id (use ANY question ID from the guide, not just the next
   sequential — but prefer sequential unless researcher intent dictates
   otherwise). probe_type and probe_triggered_by must be null.

CONVERSATIONAL RULES:
- 只用自然口语说话 — 不要 markdown、不要列表、不要编号。
- 回复要简短（一两句话）。追问比引入新话题更短。
- 如果参与者跑题，温和地把他们拉回当前问题（一句话；不要责备）。
- 当 concept_context 非空时，参与者看到的是编号（如"概念 2/3"），
  但绝不会看到内部标签。不要说"概念 A"。
- 全程使用中文与参与者对话。

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
    coverage_context: str = "",
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
        coverage_context=coverage_context.strip() or "(none)",
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
