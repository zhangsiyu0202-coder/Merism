"""Unit tests for the Sprint 1 decision validator.

Every hard rule gets a "trips" case (validator overrides LLM) and at
least one adjacent passthrough (validator lets the LLM's call stand).
"""

from __future__ import annotations

import pytest

from merism.conductor.decision_validator import validate_decision
from merism.conductor.prompts import ModeratorDecision


SECTIONS = [
    {
        "id": "s1",
        "title": "Core",
        "scope": "global",
        "questions": [
            {
                "id": "q1",
                "text": "Tell me about last week.",
                "intent": "map weekly routine",
                "probe_policy": "deep",
                "max_probes": 3,
            },
            {
                "id": "q2",
                "text": "What about yesterday?",
                "intent": "recent specifics",
                "probe_policy": "none",
                "max_probes": 1,
            },
            {
                "id": "q3",
                "text": "Any surprises?",
                "intent": "novelty",
                "probe_policy": "light",
                "max_probes": 2,
            },
        ],
    },
]


def _q(qid: str) -> dict:
    return next(q for q in SECTIONS[0]["questions"] if q["id"] == qid)


class TestRule1NoneForbidsProbe:
    """Rule 1a: probe_policy=none + followup → forced move_on."""

    def test_none_policy_blocks_probe_and_forces_move_on(self):
        decision = ModeratorDecision(
            next_action="followup",
            probe_type="expansion",
            probe_triggered_by="short answer",
        )
        result = validate_decision(
            decision,
            question=_q("q2"),
            probes_done=0,
            sections=SECTIONS,
        )
        assert result.overridden is True
        assert result.decision.next_action == "move_on"
        assert result.decision.matches_rule == 1
        assert result.decision.next_question_id == "q3"  # next after q2

    def test_none_policy_accepts_move_on(self):
        decision = ModeratorDecision(
            next_action="move_on", next_question_id="q3"
        )
        result = validate_decision(
            decision,
            question=_q("q2"),
            probes_done=0,
            sections=SECTIONS,
        )
        assert result.overridden is False


class TestRule1DeepRequiresProbe:
    """Rule 1b: probe_policy=deep AND probes_done=0 AND move_on → forced probe."""

    def test_deep_policy_forces_first_probe(self):
        decision = ModeratorDecision(next_action="move_on", next_question_id="q2")
        result = validate_decision(
            decision,
            question=_q("q1"),
            probes_done=0,
            sections=SECTIONS,
        )
        assert result.overridden is True
        assert result.decision.next_action == "followup"
        assert result.decision.matches_rule == 1
        assert result.decision.probe_type is not None

    def test_deep_policy_accepts_move_on_after_first_probe(self):
        decision = ModeratorDecision(next_action="move_on", next_question_id="q2")
        result = validate_decision(
            decision,
            question=_q("q1"),
            probes_done=1,
            sections=SECTIONS,
        )
        assert result.overridden is False


class TestRule2MaxProbesCap:
    """Rule 2: probes_done >= max_probes + followup → forced move_on."""

    def test_max_probes_forces_move_on(self):
        decision = ModeratorDecision(
            next_action="followup",
            probe_type="expansion",
            probe_triggered_by="another follow-up",
        )
        result = validate_decision(
            decision,
            question=_q("q3"),
            probes_done=2,  # equals max_probes=2
            sections=SECTIONS,
        )
        assert result.overridden is True
        assert result.decision.next_action == "move_on"
        assert result.decision.matches_rule == 2
        assert result.decision.next_question_id is None  # q3 is last

    def test_below_cap_passthrough(self):
        decision = ModeratorDecision(
            next_action="followup",
            probe_type="clarification",
            probe_triggered_by="unclear term",
        )
        result = validate_decision(
            decision,
            question=_q("q3"),
            probes_done=1,  # below cap 2
            sections=SECTIONS,
        )
        assert result.overridden is False


class TestPassthrough:
    """The validator does not alter compliant decisions."""

    @pytest.mark.parametrize(
        "qid,probes_done,action",
        [
            ("q1", 2, "followup"),  # deep policy, within cap
            ("q1", 3, "move_on"),   # deep policy, cap reached → model was right
            ("q3", 0, "move_on"),   # light policy with quick move_on is legal
            ("q2", 0, "clarify"),   # clarify always allowed
        ],
    )
    def test_compliant_decision_unchanged(self, qid: str, probes_done: int, action: str):
        decision = ModeratorDecision(
            next_action=action,  # type: ignore[arg-type]
            next_question_id="q2" if action == "move_on" else None,
            probe_type="expansion" if action == "followup" else None,
            probe_triggered_by="x" if action == "followup" else None,
        )
        result = validate_decision(
            decision,
            question=_q(qid),
            probes_done=probes_done,
            sections=SECTIONS,
        )
        assert result.overridden is False
