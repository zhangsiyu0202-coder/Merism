"""advance_cursor — pure cursor progression."""
# pyright: reportTypedDictNotRequiredAccess=false

from __future__ import annotations

from typing import Any

from merism.conductor import nodes
from merism.conductor.state import OverallState
from merism.conductor.tests.fixtures.sample_outlines import outline_3q_basic


def _state(**overrides: Any) -> OverallState:
    base: OverallState = {
        "outline": outline_3q_basic().model_dump(),
        "section_i": 0,
        "question_i": 0,
        "probe_count": 1,
        "transcript": [],
    }
    return {**base, **overrides}  # type: ignore[typeddict-item,return-value]


class TestAdvanceCursor:
    def test_within_section(self) -> None:
        # outline_3q_basic: background has 2 questions; from q[0] → q[1]
        result = nodes.advance_cursor(_state(question_i=0), {})
        assert result == {"question_i": 1, "pending_probe": None, "probe_count": 0}

    def test_section_boundary(self) -> None:
        # at end of background (q[1]) → advance to workflow s[1] q[0]
        result = nodes.advance_cursor(_state(section_i=0, question_i=1), {})
        assert result == {
            "section_i": 1,
            "question_i": 0,
            "pending_probe": None,
            "probe_count": 0,
        }

    def test_end_of_outline_marks_done(self) -> None:
        # last section, last question → done
        result = nodes.advance_cursor(_state(section_i=1, question_i=0), {})
        assert result == {"done": True, "pending_probe": None, "probe_count": 0}

    def test_probe_count_resets(self) -> None:
        # Always reset probe budget when advancing to a new question.
        result = nodes.advance_cursor(_state(question_i=0, probe_count=3), {})
        assert result["probe_count"] == 0

    def test_pending_probe_cleared(self) -> None:
        result = nodes.advance_cursor(_state(question_i=0, pending_probe="leftover"), {})
        assert result["pending_probe"] is None
