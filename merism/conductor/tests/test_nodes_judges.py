"""judge_off / judge_standard / judge_deep — 3 judge nodes + budget logic."""
# pyright: reportTypedDictNotRequiredAccess=false

from __future__ import annotations

from typing import Any

import pytest

from merism.conductor import nodes
from merism.conductor.state import OverallState
from merism.conductor.tests.fakes import FakeEvaluator
from merism.conductor.tests.fixtures.sample_outlines import outline_3q_basic
from merism.conductor.tools_and_schemas import Evaluation


def _state(**overrides: Any) -> OverallState:
    base: OverallState = {
        "outline": outline_3q_basic().model_dump(),
        "section_i": 0,
        "question_i": 0,
        "probe_count": 0,
        "transcript": [],
        "last_answer": "I'm a PM",
    }
    return {**base, **overrides}  # type: ignore[typeddict-item,return-value]


@pytest.fixture(autouse=True)
def _llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MERISM_LLM_API_KEY", "test-key")
    monkeypatch.setenv("MERISM_LLM_BASE_URL", "https://api.deepseek.com")


class TestJudgeOff:
    def test_never_calls_llm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _explode(*args: object, **kwargs: object) -> None:
            raise AssertionError("judge_off must not call LLM")

        monkeypatch.setattr(nodes, "build_llm", _explode)
        result = nodes.judge_off(_state(), {})
        assert result == {
            "pending_probe": None,
            "last_evaluation": {"sufficient": True, "skipped": True},
        }


def _patch_evaluator(monkeypatch: pytest.MonkeyPatch, *responses: Evaluation) -> FakeEvaluator:
    fake = FakeEvaluator(responses=list(responses))
    monkeypatch.setattr(nodes, "build_llm", lambda model, **kw: object())
    monkeypatch.setattr(nodes, "build_evaluator", lambda llm, schema: fake)
    return fake


class TestJudgeStandard:
    def test_sufficient_advances(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_evaluator(monkeypatch, Evaluation(sufficient=True))
        result = nodes.judge_standard(_state(), {})
        assert result["pending_probe"] is None
        assert result["last_evaluation"]["sufficient"] is True

    def test_insufficient_with_followup_probes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_evaluator(
            monkeypatch,
            Evaluation(sufficient=False, followup="What's the scope?"),
        )
        result = nodes.judge_standard(_state(), {})
        assert result["pending_probe"] == "What's the scope?"
        assert result["probe_count"] == 1

    def test_budget_exhausted_advances_anyway(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # standard_followups defaults to 2 (Configuration). probe_count=2 → at budget.
        _patch_evaluator(
            monkeypatch,
            Evaluation(sufficient=False, followup="probe"),
        )
        result = nodes.judge_standard(_state(probe_count=2), {})
        assert result["pending_probe"] is None  # advance despite insufficient

    def test_no_followup_text_advances(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Even if sufficient=False, missing followup text → engine advances
        _patch_evaluator(
            monkeypatch,
            Evaluation(sufficient=False, followup=None),
        )
        result = nodes.judge_standard(_state(), {})
        assert result["pending_probe"] is None

    def test_llm_failure_advances_with_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _explode(llm: object, schema: object) -> None:
            raise RuntimeError("LLM 503")

        monkeypatch.setattr(nodes, "build_llm", lambda model, **kw: object())
        monkeypatch.setattr(nodes, "build_evaluator", _explode)
        result = nodes.judge_standard(_state(), {})
        assert result["pending_probe"] is None
        assert result["last_error"] == "judge_call_failed"
        assert result["last_evaluation"]["sufficient"] is True  # default-advance


class TestJudgeDeep:
    def test_uses_deep_followups_budget(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # deep_followups defaults to 4 (Configuration).
        # probe_count=2 → still under budget → probe
        _patch_evaluator(
            monkeypatch,
            Evaluation(sufficient=False, followup="probe"),
        )
        result = nodes.judge_deep(_state(probe_count=2), {})
        assert result["pending_probe"] == "probe"
        assert result["probe_count"] == 3

    def test_respects_deep_budget_ceiling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # deep_followups=4. probe_count=4 → budget hit → advance.
        _patch_evaluator(
            monkeypatch,
            Evaluation(sufficient=False, followup="probe"),
        )
        result = nodes.judge_deep(_state(probe_count=4), {})
        assert result["pending_probe"] is None

    def test_uses_deep_prompt_template(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = _patch_evaluator(monkeypatch, Evaluation(sufficient=True))
        nodes.judge_deep(_state(), {})
        # JUDGE_DEEP_PROMPT contains the literal "严格"; standard does not.
        assert "严格" in fake.invocations[0]


class TestJudgeReadsProbeInstruction:
    def test_probe_instruction_passed_to_prompt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Build outline where role_context has a probe_instruction.
        from merism.conductor.schema import Outline, Question, Section

        outline = Outline(
            sections=[
                Section(
                    id="background",
                    title="Background",
                    questions=[
                        Question(
                            id="role_context",
                            ask="who are you?",
                            probe_instruction="ASK_ABOUT_TEAM_SIZE",
                        ),
                    ],
                ),
            ],
        )
        fake = _patch_evaluator(monkeypatch, Evaluation(sufficient=True))
        state: OverallState = {
            "outline": outline.model_dump(),
            "section_i": 0,
            "question_i": 0,
            "probe_count": 0,
            "transcript": [],
            "last_answer": "I'm a PM",
        }
        nodes.judge_standard(state, {})
        assert "ASK_ABOUT_TEAM_SIZE" in fake.invocations[0]

    def test_default_when_probe_instruction_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # outline_3q_basic has no probe_instruction set on any question.
        fake = _patch_evaluator(monkeypatch, Evaluation(sufficient=True))
        nodes.judge_standard(_state(), {})
        # Missing probe_instruction → "(none)" placeholder per nodes.py
        assert "(none)" in fake.invocations[0]
