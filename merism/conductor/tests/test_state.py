"""State unit tests — TypedDict shapes + operator.add reducer wiring."""

from __future__ import annotations

import operator
from typing import get_args, get_type_hints

from merism.conductor.state import (
    AdvanceOutput,
    FollowUpMode,
    JudgeOutput,
    OverallState,
)


class TestFollowUpMode:
    def test_three_modes_only(self) -> None:
        assert set(get_args(FollowUpMode)) == {"off", "standard", "deep"}


class TestOverallStateTotalFalse:
    def test_empty_dict_is_valid_state(self) -> None:
        # total=False means no key is required at construction.
        state: OverallState = {}
        assert state == {}

    def test_partial_dict_is_valid_state(self) -> None:
        state: OverallState = {"section_i": 0, "done": False}
        assert state["section_i"] == 0


class TestTranscriptReducer:
    def test_transcript_uses_operator_add(self) -> None:
        # LangGraph reads the Annotated metadata to decide how to merge
        # parallel/sequential updates. operator.add on a list = append.
        # `include_extras=True` is required because the module uses
        # `from __future__ import annotations` (PEP 563 — string-form
        # annotations); without it the Annotated metadata is stripped.
        hints = get_type_hints(OverallState, include_extras=True)
        annotation = hints["transcript"]
        assert hasattr(annotation, "__metadata__")
        assert operator.add in annotation.__metadata__

    def test_other_fields_have_no_reducer(self) -> None:
        # Default merge for non-Annotated fields = overwrite. Sanity check
        # that we didn't accidentally annotate everything.
        hints = get_type_hints(OverallState, include_extras=True)
        annotation = hints["section_i"]
        # int has no __metadata__
        assert not hasattr(annotation, "__metadata__")


class TestJudgeOutput:
    def test_total_false_partial_dict(self) -> None:
        out: JudgeOutput = {"pending_probe": None}
        assert out == {"pending_probe": None}

    def test_carries_evaluation_payload(self) -> None:
        out: JudgeOutput = {
            "pending_probe": "follow up please",
            "probe_count": 1,
            "last_evaluation": {"sufficient": False, "missing": ["frequency"]},
        }
        assert out["last_evaluation"]["sufficient"] is False


class TestAdvanceOutput:
    def test_done_field(self) -> None:
        out: AdvanceOutput = {"done": True}
        assert out["done"] is True

    def test_cursor_progression(self) -> None:
        out: AdvanceOutput = {"section_i": 1, "question_i": 0, "probe_count": 0}
        assert out["section_i"] == 1
