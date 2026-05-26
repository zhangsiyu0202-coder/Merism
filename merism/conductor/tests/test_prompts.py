"""Prompts module — verify json_mode safety constraint + format keys."""

from __future__ import annotations

import pytest

from merism.conductor.prompts import JUDGE_DEEP_PROMPT, JUDGE_STANDARD_PROMPT


class TestJsonModeSafety:
    """DeepSeek json_mode requires the literal word 'JSON' in prompt."""

    def test_judge_standard_contains_json(self) -> None:
        assert "JSON" in JUDGE_STANDARD_PROMPT

    def test_judge_deep_contains_json(self) -> None:
        assert "JSON" in JUDGE_DEEP_PROMPT


class TestJudgeStandardFormat:
    def _format(self, **overrides: str) -> str:
        defaults = {
            "ask": "what do you do?",
            "goal": "understand role",
            "must_get": "['role', 'duties']",
            "probe_instruction": "ask about scope",
            "transcript_tail": "no prior turns",
            "answer": "I'm a PM",
        }
        return JUDGE_STANDARD_PROMPT.format(**{**defaults, **overrides})

    def test_accepts_all_keys(self) -> None:
        result = self._format()
        assert "what do you do?" in result
        assert "I'm a PM" in result

    def test_missing_key_raises(self) -> None:
        with pytest.raises(KeyError):
            JUDGE_STANDARD_PROMPT.format(ask="x")  # other keys missing


class TestJudgeDeepFormat:
    def test_accepts_same_keys_as_standard(self) -> None:
        # Both judge prompts share the same format keys so the shared
        # _judge_with_prompt helper can call either.
        result = JUDGE_DEEP_PROMPT.format(
            ask="ask",
            goal="goal",
            must_get="[]",
            probe_instruction="instruction",
            transcript_tail="tail",
            answer="answer",
        )
        assert "ask" in result
        assert "answer" in result


class TestPromptStructure:
    def test_all_prompts_are_strings(self) -> None:
        for prompt in (JUDGE_STANDARD_PROMPT, JUDGE_DEEP_PROMPT):
            assert isinstance(prompt, str)
            assert len(prompt) > 100  # non-trivial content

    def test_judge_prompts_distinguish_strictness(self) -> None:
        # Standard mentions "大多数" / "宽松"; deep mentions "严格" / "每一点".
        assert "宽松" in JUDGE_STANDARD_PROMPT or "大多数" in JUDGE_STANDARD_PROMPT
        assert "严格" in JUDGE_DEEP_PROMPT
        assert "每一点" in JUDGE_DEEP_PROMPT
