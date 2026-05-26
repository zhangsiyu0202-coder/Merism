"""Schema unit tests — Pydantic field validation + structural invariants."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from merism.conductor.schema import (
    Outline,
    OutlineError,
    Question,
    Section,
    find_question,
    flatten_questions,
    validate_outline,
)


def _q(qid: str = "q1", **kw: object) -> Question:
    return Question.model_validate({"id": qid, "ask": "ask?", **kw})


def _s(sid: str = "s1", *, qs: list[Question] | None = None) -> Section:
    if qs is None:
        qs = [_q()]
    return Section(id=sid, title="title", questions=qs)


def _o(*sections: Section) -> Outline:
    return Outline(sections=list(sections))


class TestQuestion:
    def test_minimal_valid(self) -> None:
        q = _q()
        assert q.id == "q1"
        assert q.follow_up_mode == "standard"
        assert q.probe_instruction is None

    def test_id_pattern_rejects_dash(self) -> None:
        with pytest.raises(ValidationError):
            Question(id="bad-id", ask="a")

    def test_id_pattern_rejects_space(self) -> None:
        with pytest.raises(ValidationError):
            Question(id="bad space", ask="a")

    def test_id_pattern_accepts_underscore_and_digits(self) -> None:
        assert _q("role_context_42").id == "role_context_42"

    def test_extra_field_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            Question(id="q1", ask="a", surprise="x")  # type: ignore[call-arg]

    def test_empty_ask_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _q(ask="")

    def test_follow_up_mode_default_standard(self) -> None:
        assert _q().follow_up_mode == "standard"

    def test_follow_up_mode_off(self) -> None:
        assert _q(follow_up_mode="off").follow_up_mode == "off"

    def test_follow_up_mode_deep(self) -> None:
        assert _q(follow_up_mode="deep").follow_up_mode == "deep"

    def test_follow_up_mode_invalid_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _q(follow_up_mode="weird")

    def test_probe_instruction_optional(self) -> None:
        q = _q(probe_instruction="dig deeper on frequency")
        assert q.probe_instruction == "dig deeper on frequency"


class TestSection:
    def test_id_pattern_enforced(self) -> None:
        with pytest.raises(ValidationError):
            Section(id="bad id", title="t", questions=[])

    def test_extra_field_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            Section(id="s1", title="t", questions=[], surprise="x")  # type: ignore[call-arg]

    def test_empty_title_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Section(id="s1", title="", questions=[])


class TestOutline:
    def test_default_empty(self) -> None:
        o = Outline()
        assert o.version == "v3"
        assert o.sections == []

    def test_version_locked(self) -> None:
        with pytest.raises(ValidationError):
            Outline.model_validate({"version": "v2", "sections": []})

    def test_extra_field_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            Outline.model_validate({"version": "v3", "sections": [], "extra_field": True})

    def test_round_trip_via_model_dump(self) -> None:
        outline = _o(_s("s1", qs=[_q("q1", probe_instruction="x")]))
        payload = outline.model_dump()
        assert payload["version"] == "v3"
        rebuilt = Outline.model_validate(payload)
        assert rebuilt == outline


class TestValidateOutline:
    def test_passes_minimal(self) -> None:
        validate_outline(_o(_s("s1", qs=[_q("q1")])))

    def test_rejects_duplicate_section_id(self) -> None:
        outline = _o(_s("s1", qs=[_q("q1")]), _s("s1", qs=[_q("q2")]))
        with pytest.raises(OutlineError, match="duplicate section id"):
            validate_outline(outline)

    def test_rejects_duplicate_question_id_across_sections(self) -> None:
        outline = _o(_s("s1", qs=[_q("q1")]), _s("s2", qs=[_q("q1")]))
        with pytest.raises(OutlineError, match="duplicate question id"):
            validate_outline(outline)

    def test_rejects_empty_section(self) -> None:
        outline = _o(_s("s1", qs=[]))
        with pytest.raises(OutlineError, match="no questions"):
            validate_outline(outline)


class TestFlattenQuestions:
    def test_preserves_order(self) -> None:
        outline = _o(
            _s("s1", qs=[_q("q1"), _q("q2")]),
            _s("s2", qs=[_q("q3")]),
        )
        flat = flatten_questions(outline)
        assert [q.id for _, q in flat] == ["q1", "q2", "q3"]
        assert [s.id for s, _ in flat] == ["s1", "s1", "s2"]

    def test_empty_outline_returns_empty(self) -> None:
        assert flatten_questions(Outline()) == []


class TestFindQuestion:
    def test_returns_match(self) -> None:
        outline = _o(_s("s1", qs=[_q("q1"), _q("q2")]))
        result = find_question(outline, "q2")
        assert result is not None
        section, question = result
        assert section.id == "s1"
        assert question.id == "q2"

    def test_returns_none_on_miss(self) -> None:
        outline = _o(_s("s1", qs=[_q("q1")]))
        assert find_question(outline, "nope") is None
