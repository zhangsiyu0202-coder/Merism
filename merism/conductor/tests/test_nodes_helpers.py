"""Helpers in nodes.py — pure-function tests, no LLM."""

from __future__ import annotations

import pytest

from merism.conductor.nodes import (
    _current_section_and_question,
    _format_transcript_tail,
    _outline_from_state,
)
from merism.conductor.schema import Turn
from merism.conductor.state import OverallState
from merism.conductor.tests.fixtures.sample_outlines import outline_3q_basic


def _state(**overrides: object) -> OverallState:
    base: OverallState = {
        "outline": outline_3q_basic().model_dump(),
        "section_i": 0,
        "question_i": 0,
        "transcript": [],
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


class TestOutlineFromState:
    def test_loads_pydantic_outline(self) -> None:
        outline = _outline_from_state(_state())
        assert outline.version == "v3"
        assert len(outline.sections) == 2

    def test_raises_when_outline_missing(self) -> None:
        with pytest.raises(RuntimeError, match="missing 'outline'"):
            _outline_from_state({})


class TestCurrentSectionAndQuestion:
    def test_initial_cursor_returns_first_question(self) -> None:
        section, question = _current_section_and_question(_state())
        assert section.id == "background"
        assert question.id == "role_context"

    def test_advanced_cursor_within_section(self) -> None:
        section, question = _current_section_and_question(_state(section_i=0, question_i=1))
        assert section.id == "background"
        assert question.id == "current_problem"

    def test_advanced_cursor_across_sections(self) -> None:
        section, question = _current_section_and_question(_state(section_i=1, question_i=0))
        assert section.id == "workflow"
        assert question.id == "current_process"


def _turn(section_id: str, question_id: str, kind: str = "main", *, q: str = "Q?", a: str = "A.") -> Turn:
    return {
        "section_id": section_id,
        "question_id": question_id,
        "kind": kind,  # type: ignore[typeddict-item]
        "question": q,
        "answer": a,
    }


class TestFormatTranscriptTail:
    def test_empty_transcript(self) -> None:
        assert _format_transcript_tail(_state()) == "(no prior turns)"

    def test_truncates_to_n(self) -> None:
        turns = [_turn("s1", f"q{i}", q=f"q{i}?", a=f"a{i}") for i in range(10)]
        out = _format_transcript_tail(_state(transcript=turns), n=2)
        assert "q9?" in out  # last turn present
        assert "q0?" not in out  # earliest dropped
        assert out.count("Q (") == 2

    def test_includes_followup_kind(self) -> None:
        turns = [_turn("s1", "q1", "followup", q="probe?", a="ok.")]
        out = _format_transcript_tail(_state(transcript=turns))
        assert "(followup)" in out
