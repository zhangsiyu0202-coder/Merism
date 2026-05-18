from __future__ import annotations

from merism.conductor.generation_prompt import build_generation_prompt


def test_build_generation_prompt_includes_probe_context() -> None:
    messages = build_generation_prompt(
        decision_next_action="followup",
        decision_probe_type="expansion",
        decision_probe_kind="preset",
        decision_dynamic_trigger=None,
        probe_policy="light",
        probes_done=1,
        max_probes=3,
        remaining_followups=2,
        phase="active",
        closing_rounds_remaining=0,
        decision_target_goal_id=None,
        decision_off_topic=False,
        decision_steering_strategy="deepen_current",
        decision_think_notes="The participant gave a short answer.",
        current_question_text="Tell me about how you chose it.",
        next_question_text="",
        target_goal_text="",
        recent_turns="Participant: It was okay.",
        participant_latest="It was okay.",
        probe_directions=["specific examples", "friction"],
    )

    system_prompt = str(messages[0]["content"])
    user_prompt = str(messages[1]["content"])

    assert "do not force a canned opener" in system_prompt.lower()
    assert "ALWAYS start with a short filler acknowledgement" not in system_prompt
    assert "probe_policy:" in user_prompt
    assert "probes_done:" in user_prompt
    assert "max_probes:" in user_prompt
    assert "remaining:" in user_prompt
    assert "phase:" in user_prompt
    assert "closing_rounds_remaining:" in user_prompt
    assert "probe_directions:" in user_prompt
