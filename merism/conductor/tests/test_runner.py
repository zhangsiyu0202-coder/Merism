"""Runner — start_interview, answer_interview, get_interrupt_payload."""
# pyright: reportTypedDictNotRequiredAccess=false

from __future__ import annotations

from typing import ClassVar

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from merism.conductor import nodes
from merism.conductor.graph import build_graph
from merism.conductor.runner import (
    answer_interview,
    get_interrupt_payload,
    graph_config,
    start_interview,
)
from merism.conductor.tests.fakes import FakeEvaluator
from merism.conductor.tests.fixtures.sample_outlines import outline_3q_basic
from merism.conductor.tools_and_schemas import Evaluation


@pytest.fixture(autouse=True)
def _llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MERISM_LLM_API_KEY", "test-key")
    monkeypatch.setenv("MERISM_LLM_BASE_URL", "https://api.deepseek.com")


class TestGraphConfig:
    def test_basic_config(self) -> None:
        assert graph_config("session-123") == {"configurable": {"thread_id": "session-123"}}

    def test_with_extra_configurable(self) -> None:
        cfg = graph_config("s1", configurable={"judge_model": "deepseek-reasoner"})
        assert cfg["configurable"]["thread_id"] == "s1"
        assert cfg["configurable"]["judge_model"] == "deepseek-reasoner"


class TestGetInterruptPayload:
    def test_none_when_no_interrupt(self) -> None:
        assert get_interrupt_payload({}) is None
        assert get_interrupt_payload({"final_report": "done"}) is None

    def test_extracts_value_attribute(self) -> None:
        class _IntObj:
            value: ClassVar[dict[str, str]] = {"question": "what?"}

        result = {"__interrupt__": [_IntObj()]}
        payload = get_interrupt_payload(result)
        assert payload == {"question": "what?"}

    def test_extracts_value_dict_key(self) -> None:
        result = {"__interrupt__": [{"value": {"question": "what?"}}]}
        payload = get_interrupt_payload(result)
        assert payload == {"question": "what?"}

    def test_returns_dict_directly_when_no_value_wrapper(self) -> None:
        result = {"__interrupt__": [{"question": "what?"}]}
        payload = get_interrupt_payload(result)
        assert payload == {"question": "what?"}


class TestStartInterviewOffMode:
    """End-to-end smoke: outline_3q_basic in 'off' mode walks all 3 questions
    with no LLM calls (judge_off bypasses the LLM)."""

    def test_first_turn_yields_first_question(self, monkeypatch: pytest.MonkeyPatch) -> None:
        graph = build_graph(checkpointer=InMemorySaver())
        result = start_interview(
            graph,
            outline=outline_3q_basic(follow_up_mode="off"),
            thread_id="t1",
            follow_up_mode="off",
        )
        payload = get_interrupt_payload(result)
        assert payload is not None
        assert payload["section_id"] == "background"
        assert payload["question_id"] == "role_context"
        assert payload["kind"] == "main"

    def test_full_walk_through_three_questions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        graph = build_graph(checkpointer=InMemorySaver())
        result = start_interview(
            graph,
            outline=outline_3q_basic(follow_up_mode="off"),
            thread_id="t-full",
            follow_up_mode="off",
        )
        seen_question_ids: list[str] = []
        for _ in range(10):  # safety bound
            payload = get_interrupt_payload(result)
            if payload is None:
                break
            seen_question_ids.append(payload["question_id"])
            result = answer_interview(graph, user_answer="ok", thread_id="t-full")

        # Expect exactly 3 main questions in outline order.
        assert seen_question_ids == ["role_context", "current_problem", "current_process"]
        # After last question, graph reaches END → no interrupt
        assert get_interrupt_payload(result) is None


class TestStartInterviewStandardMode:
    """Standard mode uses judge_standard which calls the LLM. Mock the
    evaluator so we can drive the graph deterministically."""

    def test_judge_says_sufficient_advances(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Three sufficient evaluations → 3 main questions, no probes.
        fake = FakeEvaluator(
            responses=[
                Evaluation(sufficient=True),
                Evaluation(sufficient=True),
                Evaluation(sufficient=True),
            ]
        )
        monkeypatch.setattr(nodes, "build_llm", lambda model, **kw: object())
        monkeypatch.setattr(nodes, "build_evaluator", lambda llm, schema: fake)

        graph = build_graph(checkpointer=InMemorySaver())
        result = start_interview(
            graph,
            outline=outline_3q_basic(),
            thread_id="t-std",
            follow_up_mode="standard",
        )
        seen: list[str] = []
        for _ in range(10):
            payload = get_interrupt_payload(result)
            if payload is None:
                break
            seen.append(payload["question_id"])
            result = answer_interview(graph, user_answer="answer", thread_id="t-std")

        assert seen == ["role_context", "current_problem", "current_process"]
        # Graph reached END (no finalize node; transcript is the only payload)
        assert result.get("done") is True
        assert len(result.get("transcript", [])) == 3


class TestStartInterviewProbeLoop:
    """Standard mode where judge requests one probe, then sufficient."""

    def test_one_probe_then_advance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_eval = FakeEvaluator(
            responses=[
                # q1: needs probe
                Evaluation(sufficient=False, followup="What scope?"),
                # q1: probe satisfied
                Evaluation(sufficient=True),
                # q2: sufficient first try
                Evaluation(sufficient=True),
                # q3: sufficient first try
                Evaluation(sufficient=True),
            ]
        )
        monkeypatch.setattr(nodes, "build_llm", lambda model, **kw: object())
        monkeypatch.setattr(nodes, "build_evaluator", lambda llm, schema: fake_eval)

        graph = build_graph(checkpointer=InMemorySaver())
        result = start_interview(
            graph,
            outline=outline_3q_basic(),
            thread_id="t-probe",
            follow_up_mode="standard",
        )
        seen_questions: list[tuple[str, str]] = []  # (qid, kind)
        for _ in range(10):
            payload = get_interrupt_payload(result)
            if payload is None:
                break
            seen_questions.append((payload["question_id"], payload["kind"]))
            result = answer_interview(graph, user_answer="ans", thread_id="t-probe")

        # Expect: role_context (main), role_context (followup), current_problem (main), current_process (main)
        assert seen_questions == [
            ("role_context", "main"),
            ("role_context", "followup"),
            ("current_problem", "main"),
            ("current_process", "main"),
        ]
        # All 4 evaluator responses consumed
        assert fake_eval._responses == []  # type: ignore[attr-defined]
