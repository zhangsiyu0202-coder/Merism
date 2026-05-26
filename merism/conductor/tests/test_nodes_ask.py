"""ask_and_wait — interrupt() emission + transcript turn append."""
# pyright: reportTypedDictNotRequiredAccess=false

from __future__ import annotations

from typing import Any

import pytest

from merism.conductor import nodes
from merism.conductor.state import OverallState
from merism.conductor.tests.fixtures.sample_outlines import outline_3q_basic


def _state(**overrides: Any) -> OverallState:
    base: OverallState = {
        "outline": outline_3q_basic().model_dump(),
        "section_i": 0,
        "question_i": 0,
        "transcript": [],
    }
    return {**base, **overrides}  # type: ignore[typeddict-item,return-value]


class TestAskAndWait:
    def test_emits_main_question_payload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[dict[str, Any]] = []

        def _fake_interrupt(payload: dict[str, Any]) -> str:
            captured.append(payload)
            return "user reply text"

        monkeypatch.setattr(nodes, "interrupt", _fake_interrupt)
        result = nodes.ask_and_wait(_state(), {})

        assert len(captured) == 1
        payload = captured[0]
        assert payload["section_id"] == "background"
        assert payload["question_id"] == "role_context"
        assert payload["kind"] == "main"
        assert payload["question"] == "先介绍一下你现在的角色?"

        assert result["last_answer"] == "user reply text"
        assert len(result["transcript"]) == 1
        turn = result["transcript"][0]
        assert turn["kind"] == "main"
        assert turn["answer"] == "user reply text"

    def test_emits_probe_when_pending_probe_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[dict[str, Any]] = []

        def _fake_interrupt(payload: dict[str, Any]) -> str:
            captured.append(payload)
            return "second answer"

        monkeypatch.setattr(nodes, "interrupt", _fake_interrupt)
        state = _state(pending_probe="probe text?")
        result = nodes.ask_and_wait(state, {})

        assert captured[0]["kind"] == "followup"
        assert captured[0]["question"] == "probe text?"
        assert result["transcript"][0]["kind"] == "followup"
        assert result["transcript"][0]["question"] == "probe text?"

    def test_returns_only_new_turn_for_reducer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Critical: state has 5 prior turns, but node returns [1 turn].
        # The operator.add reducer in OverallState.transcript is what
        # appends; node must NOT return the full list.
        monkeypatch.setattr(nodes, "interrupt", lambda payload: "ans")
        prior_turns = [
            {
                "section_id": "s",
                "question_id": "q",
                "kind": "main",
                "question": f"Q{i}",
                "answer": f"A{i}",
            }
            for i in range(5)
        ]
        result = nodes.ask_and_wait(_state(transcript=prior_turns), {})
        # Node returns only ONE new turn, not the full list.
        assert len(result["transcript"]) == 1
