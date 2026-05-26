"""Pydantic models for LLM structured output."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from merism.conductor.tools_and_schemas import Evaluation


class TestEvaluation:
    def test_minimal_sufficient(self) -> None:
        ev = Evaluation(sufficient=True)
        assert ev.sufficient is True
        assert ev.followup is None
        assert ev.reason == ""

    def test_full_insufficient(self) -> None:
        ev = Evaluation(
            sufficient=False,
            followup="多久发生一次?",
            reason="user only described type of problem",
        )
        assert ev.sufficient is False
        assert ev.followup is not None

    def test_extra_field_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            Evaluation(sufficient=True, surprise="x")  # type: ignore[call-arg]

    def test_missing_required_field_raises(self) -> None:
        with pytest.raises(ValidationError):
            Evaluation()  # type: ignore[call-arg]

    def test_round_trip_via_model_dump(self) -> None:
        ev = Evaluation(sufficient=False, followup="y", reason="z")
        rebuilt = Evaluation.model_validate(ev.model_dump())
        assert rebuilt == ev
