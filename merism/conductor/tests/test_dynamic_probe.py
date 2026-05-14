"""Tests for dual-layer (preset + dynamic) probe validation rules."""

from merism.conductor.decision_validator import validate_decision
from merism.conductor.prompts import ModeratorDecision


def _q(probe_policy="light", max_probes=2, dynamic_probe=None):
    q = {"id": "q1", "text": "Test?", "probe_policy": probe_policy, "max_probes": max_probes}
    if dynamic_probe is not None:
        q["dynamic_probe"] = dynamic_probe
    return q


SECTIONS = [{"id": "s1", "questions": [
    {"id": "q1", "text": "Q1"},
    {"id": "q2", "text": "Q2"},
]}]


class TestDynamicProbeRule3:
    def test_dynamic_probe_blocked_when_not_enabled(self):
        decision = ModeratorDecision(
            next_action="followup", probe_type="expansion",
            probe_kind="dynamic", dynamic_trigger="new_theme",
            probe_triggered_by="found new theme",
        )
        result = validate_decision(
            decision, question=_q(dynamic_probe={"enabled": False}),
            probes_done=0, sections=SECTIONS,
        )
        assert result.overridden
        assert result.decision.next_action == "followup"
        assert "downgraded to preset" in result.reason

    def test_dynamic_probe_blocked_forces_move_on_when_preset_exhausted(self):
        decision = ModeratorDecision(
            next_action="followup", probe_type="expansion",
            probe_kind="dynamic", dynamic_trigger="new_theme",
            probe_triggered_by="found new theme",
        )
        result = validate_decision(
            decision, question=_q(max_probes=2, dynamic_probe={"enabled": False}),
            probes_done=2, sections=SECTIONS,
        )
        assert result.overridden
        assert result.decision.next_action == "move_on"


class TestDynamicProbeRule4:
    def test_missing_trigger_is_invalid(self):
        decision = ModeratorDecision(
            next_action="followup", probe_type="expansion",
            probe_kind="dynamic", probe_triggered_by="found something new",
        )
        result = validate_decision(
            decision,
            question=_q(dynamic_probe={"enabled": True, "max_extra_rounds": 2, "triggers": ["new_theme"]}),
            probes_done=0, sections=SECTIONS,
        )
        assert result.overridden
        assert "required" in result.reason

    def test_trigger_not_in_allowed_list(self):
        decision = ModeratorDecision(
            next_action="followup", probe_type="expansion",
            probe_kind="dynamic", dynamic_trigger="contradiction",
            probe_triggered_by="contradicted earlier",
        )
        result = validate_decision(
            decision,
            question=_q(dynamic_probe={"enabled": True, "max_extra_rounds": 2, "triggers": ["new_theme"]}),
            probes_done=0, sections=SECTIONS,
        )
        assert result.overridden
        assert "not in" in result.reason


class TestDynamicProbeRule5:
    def test_dynamic_budget_exhausted(self):
        decision = ModeratorDecision(
            next_action="followup", probe_type="expansion",
            probe_kind="dynamic", dynamic_trigger="new_theme",
            probe_triggered_by="new theme found",
        )
        result = validate_decision(
            decision,
            question=_q(dynamic_probe={"enabled": True, "max_extra_rounds": 1, "triggers": ["new_theme"]}),
            probes_done=2, sections=SECTIONS, dynamic_probes_done=1,
        )
        assert result.overridden
        assert result.decision.next_action == "move_on"
        assert "exhausted" in result.reason


class TestDynamicProbeAllowed:
    def test_valid_dynamic_probe_passes(self):
        decision = ModeratorDecision(
            next_action="followup", probe_type="expansion",
            probe_kind="dynamic", dynamic_trigger="new_theme",
            probe_triggered_by="participant mentioned new pain point",
        )
        result = validate_decision(
            decision,
            question=_q(max_probes=2, dynamic_probe={"enabled": True, "max_extra_rounds": 2, "triggers": ["new_theme", "contradiction"]}),
            probes_done=2, sections=SECTIONS, dynamic_probes_done=0,
        )
        assert not result.overridden
        assert result.decision.next_action == "followup"

    def test_preset_exhausted_but_dynamic_available_allows_followup(self):
        decision = ModeratorDecision(
            next_action="followup", probe_type="expansion",
            probe_kind="dynamic", dynamic_trigger="surprise_finding",
            probe_triggered_by="unexpected insight",
        )
        result = validate_decision(
            decision,
            question=_q(max_probes=1, dynamic_probe={"enabled": True, "max_extra_rounds": 1, "triggers": ["surprise_finding"]}),
            probes_done=1, sections=SECTIONS, dynamic_probes_done=0,
        )
        assert not result.overridden
