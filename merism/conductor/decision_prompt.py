"""Decision-phase prompt for the voice moderator.

Used by the `coverage_steer` node in the 2-node LangGraph. Asks the LLM
to produce ONLY a structured decision (no natural-language output) based
on the current turn's context + coverage state + probe policy.

Keep this prompt SHORT — the model should spend tokens on reasoning,
not regurgitating the system instructions.
"""

from __future__ import annotations


DECISION_SYSTEM_PROMPT = """\
You are the decision layer of an interview moderator.

You will be given:
- The research goal + current question with its probe policy
- The participant's latest message + last few turns of context
- Under-covered study goals (coverage gaps)

Your task: decide the next moderator action. DO NOT write the reply itself — a separate layer will generate the spoken response from your decision.

Output a single JSON object matching this schema:

{
  "next_action": "followup" | "move_on" | "clarify" | "close",
  "next_question_id": "<question id if move_on, else null>",
  "probe_type": "expansion" | "clarification" | "feeling" | "reasoning" | null,
  "probe_triggered_by": "<short human reason if followup, else null>",
  "target_goal_id": "<study goal id you are steering toward, or null>",
  "off_topic": <true if participant's last message is off-topic, else false>,
  "steering_strategy": "deepen_current" | "redirect_to_goal" | "advance" | "close_now",
  "think_notes": "<1-2 sentences: what did the answer reveal? why this action?>",
  "matches_rule": <1..4 — which DECISION RULE below you followed>
}

DECISION RULES (non-negotiable — the server enforces these):
1. Respect probe_policy:
   - "none":  NEVER followup. Always move_on (or close if guide ends).
   - "light": Only followup when the reply is vague/short/contradictory.
   - "deep":  Must followup at least once per question.
2. If probes_done >= max_probes → MUST move_on. Never exceed the cap.
3. If next_action = "followup":
   - probe_type + probe_triggered_by are required.
   - steering_strategy should be "deepen_current" normally, or "redirect_to_goal" if covering a gap matters more.
4. If next_action = "move_on":
   - next_question_id is required (pick from guide). Prefer sequential unless an under-covered goal dictates a jump.
   - probe_type must be null.

COVERAGE STEERING:
- When under-covered goals exist AND the participant opened a door (mentioned something relevant), BIAS toward followup/move_on that hits that goal. Set target_goal_id to the matching goal id.
- When the participant is clearly off-topic, set off_topic=true. The steering_strategy becomes "redirect_to_goal" (pick a goal they can answer).

Return ONLY the JSON. No prose, no markdown fences."""


DECISION_USER_TEMPLATE = """\
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

<coverage_context>
{coverage_context}
</coverage_context>

<recent_turns>
{recent_turns}
</recent_turns>

<participant_latest>
{participant_latest}
</participant_latest>

Produce the decision JSON now."""


def build_decision_prompt(
    *,
    research_goal: str,
    question_id: str,
    question_text: str,
    intent: str,
    probe_policy: str,
    probes_done: int,
    max_probes: int,
    current_stimulus: str,
    concept_context: str,
    coverage_context: str,
    recent_turns: str,
    participant_latest: str,
) -> list[dict[str, str]]:
    """Return the OpenAI-compatible chat messages for the decision phase."""
    remaining = max(0, max_probes - probes_done)
    user_msg = DECISION_USER_TEMPLATE.format(
        research_goal=research_goal.strip() or "(not set)",
        question_id=question_id or "(unset)",
        question_text=(question_text or "").strip() or "(empty)",
        intent=(intent or "").strip() or "(not specified)",
        probe_policy=probe_policy,
        probes_done=probes_done,
        max_probes=max_probes,
        remaining=remaining,
        current_stimulus=current_stimulus.strip() or "(none)",
        concept_context=concept_context.strip() or "(none)",
        coverage_context=coverage_context.strip() or "(none)",
        recent_turns=recent_turns.strip() or "(none — first turn)",
        participant_latest=participant_latest.strip(),
    )
    return [
        {"role": "system", "content": DECISION_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
