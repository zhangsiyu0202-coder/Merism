"""Routing functions — pure state -> Literal[node_name] dispatch."""
# pyright: reportTypedDictNotRequiredAccess=false

from __future__ import annotations

from merism.conductor.graph import (
    route_after_advance,
    route_after_ask,
    route_after_judge,
)


class TestRouteAfterAsk:
    """``route_after_ask`` reads ``follow_up_mode`` from the current question
    in the outline (per-question) — falls back to session-level if outline
    can't be resolved (defensive)."""

    def _state_with_mode(self, mode: str) -> dict:
        # Build a minimal outline state with one question carrying ``mode``.
        return {
            "outline": {
                "version": "v3",
                "sections": [
                    {
                        "id": "s1",
                        "title": "S",
                        "questions": [
                            {
                                "id": "q1",
                                "ask": "x",
                                "follow_up_mode": mode,
                                "probe_instruction": None,
                            }
                        ],
                    }
                ],
            },
            "section_i": 0,
            "question_i": 0,
        }

    def test_off_routes_to_judge_off(self) -> None:
        assert route_after_ask(self._state_with_mode("off")) == "judge_off"

    def test_standard_routes_to_judge_standard(self) -> None:
        assert route_after_ask(self._state_with_mode("standard")) == "judge_standard"

    def test_deep_routes_to_judge_deep(self) -> None:
        assert route_after_ask(self._state_with_mode("deep")) == "judge_deep"

    def test_default_when_no_outline(self) -> None:
        # No outline + no session mode → standard (engine default)
        assert route_after_ask({}) == "judge_standard"

    def test_falls_back_to_session_mode_when_outline_invalid(self) -> None:
        # outline missing the requested cursor → fallback to state.follow_up_mode
        state = {
            "outline": {"version": "v3", "sections": []},
            "section_i": 0,
            "question_i": 0,
            "follow_up_mode": "deep",
        }
        # No question at [0][0] — fallback to session mode
        assert route_after_ask(state) == "judge_deep"  # type: ignore[arg-type]


class TestRouteAfterJudge:
    def test_pending_probe_loops_to_ask(self) -> None:
        assert route_after_judge({"pending_probe": "probe text?"}) == "ask"

    def test_no_pending_probe_advances(self) -> None:
        assert route_after_judge({"pending_probe": None}) == "advance"

    def test_missing_pending_probe_advances(self) -> None:
        assert route_after_judge({}) == "advance"

    def test_empty_string_probe_advances(self) -> None:
        # Empty string is falsy → advance (LLM occasionally emits empty followup).
        assert route_after_judge({"pending_probe": ""}) == "advance"


class TestRouteAfterAdvance:
    def test_done_routes_to_end(self) -> None:
        assert route_after_advance({"done": True}) == "__end__"

    def test_not_done_loops_to_ask(self) -> None:
        assert route_after_advance({"done": False}) == "ask"

    def test_missing_done_loops_to_ask(self) -> None:
        assert route_after_advance({}) == "ask"
