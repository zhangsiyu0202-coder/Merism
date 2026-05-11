"""Tests for :mod:`merism.conductor.llm_polish`.

The polish pipeline calls DeepSeek with ``response_format=json_object``.
We stub the client with a minimal fake that mimics the OpenAI SDK's
``client.chat.completions.create(...)`` async call + returns a
completion-shaped object.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import patch

import pytest

from merism.conductor.llm_polish import polish_session_turns


# ── Minimal fake of openai.AsyncOpenAI shape ────────────────────

@dataclass
class _FakeMessage:
    content: str


@dataclass
class _FakeChoice:
    message: _FakeMessage


@dataclass
class _FakeCompletion:
    choices: list[_FakeChoice]


class _FakeAsyncCompletions:
    def __init__(self, response_body: str) -> None:
        self._response_body = response_body
        self.call_count = 0
        self.last_kwargs: dict[str, Any] = {}

    async def create(self, **kwargs: Any) -> _FakeCompletion:
        self.call_count += 1
        self.last_kwargs = kwargs
        return _FakeCompletion(
            choices=[_FakeChoice(message=_FakeMessage(content=self._response_body))]
        )


class _FakeChat:
    def __init__(self, completions: _FakeAsyncCompletions) -> None:
        self.completions = completions


class _FakeClient:
    def __init__(self, response_body: str) -> None:
        self.chat = _FakeChat(_FakeAsyncCompletions(response_body))


def _make_fake_client(polished_turns: list[dict[str, Any]]) -> _FakeClient:
    body = json.dumps({"turns": polished_turns}, ensure_ascii=False)
    return _FakeClient(body)


# ── Tests ───────────────────────────────────────────────────────

class TestHappyPath:
    @pytest.mark.asyncio
    async def test_polishes_participant_turns_only(self):
        turns = [
            {"role": "agent", "text": "你好，欢迎参加访谈。"},
            {"role": "participant", "text": "嗯嗯，我，我觉得这个功能挺好用的。"},
            {"role": "agent", "text": "能说说哪里好用吗？"},
            {"role": "participant", "text": "就是说，那个搜索比以前快多了。"},
        ]
        fake = _make_fake_client([
            {"index": 1, "text_clean": "我觉得这个功能挺好用的。"},
            {"index": 3, "text_clean": "那个搜索比以前快多了。"},
        ])

        with patch("merism.conductor.llm_polish.get_llm", return_value=fake):
            out = await polish_session_turns(turns)

        assert len(out) == 4
        # Agent turns pass through untouched by LLM (but still pre-cleaned).
        assert out[0]["role"] == "agent"
        assert out[0]["text_clean"] == "你好，欢迎参加访谈。"
        # Participant turns got LLM-polished.
        assert out[1]["text_clean"] == "我觉得这个功能挺好用的。"
        assert out[3]["text_clean"] == "那个搜索比以前快多了。"
        # text_raw preserved on every turn.
        assert out[1]["text_raw"] == "嗯嗯，我，我觉得这个功能挺好用的。"
        # Legacy mirror: ``text`` field updated.
        assert out[1]["text"] == "我觉得这个功能挺好用的。"

    @pytest.mark.asyncio
    async def test_batch_fires_only_once(self):
        turns = [
            {"role": "participant", "text": "第一句话，嗯嗯，还算清楚。"},
            {"role": "participant", "text": "第二句话，啊，也是清楚的。"},
            {"role": "participant", "text": "第三句话，就是说还不错。"},
        ]
        fake = _make_fake_client([
            {"index": 0, "text_clean": "第一句话还算清楚。"},
            {"index": 1, "text_clean": "第二句话也是清楚的。"},
            {"index": 2, "text_clean": "第三句话还不错。"},
        ])

        with patch("merism.conductor.llm_polish.get_llm", return_value=fake):
            await polish_session_turns(turns)

        # One LLM call for three turns — batching is the point.
        assert fake.chat.completions.call_count == 1


class TestFallback:
    @pytest.mark.asyncio
    async def test_llm_raises_falls_back_to_rule_clean(self):
        turns = [
            {"role": "participant", "text": "嗯嗯，我，我，我觉得还不错。"},
        ]

        class _Exploding:
            async def create(self, **kwargs: Any) -> Any:
                raise RuntimeError("LLM unavailable")

        fake = _FakeClient("")
        fake.chat.completions = _Exploding()  # type: ignore[assignment]

        with patch("merism.conductor.llm_polish.get_llm", return_value=fake):
            out = await polish_session_turns(turns)

        assert len(out) == 1
        # Rule-cleaned fallback still populated.
        assert "我觉得还不错" in out[0]["text_clean"]
        assert out[0]["text_raw"] == "嗯嗯，我，我，我觉得还不错。"

    @pytest.mark.asyncio
    async def test_llm_returns_wrong_index_set_falls_back(self):
        turns = [
            {"role": "participant", "text": "第一条，嗯嗯。"},
            {"role": "participant", "text": "第二条，啊。"},
        ]
        # Returns only index 0 — mismatch triggers fallback.
        fake = _make_fake_client([{"index": 0, "text_clean": "第一条。"}])

        with patch("merism.conductor.llm_polish.get_llm", return_value=fake):
            out = await polish_session_turns(turns)

        # Both turns get rule-cleaned fallback, not the partial LLM output.
        assert out[0]["text_clean"] == "第一条。"  # rule_clean strips "嗯嗯"
        assert out[1]["text_clean"] == "第二条。"


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_transcript(self):
        out = await polish_session_turns([])
        assert out == []

    @pytest.mark.asyncio
    async def test_short_turn_skipped_by_llm(self):
        turns = [{"role": "participant", "text": "是。"}]
        called = {"v": 0}

        class _Counting:
            async def create(self, **kwargs: Any) -> Any:
                called["v"] += 1
                return _FakeCompletion(
                    choices=[_FakeChoice(message=_FakeMessage(content='{"turns": []}'))]
                )

        fake = _FakeClient("")
        fake.chat.completions = _Counting()  # type: ignore[assignment]

        with patch("merism.conductor.llm_polish.get_llm", return_value=fake):
            out = await polish_session_turns(turns)

        # "是。" is <6 chars after rule_clean → no LLM call.
        assert called["v"] == 0
        assert out[0]["text_clean"] == "是。"

    @pytest.mark.asyncio
    async def test_system_role_untouched(self):
        turns = [
            {"role": "system", "text": "Session started"},
            {"role": "participant", "text": "嗯嗯，还不错"},
        ]
        fake = _make_fake_client([{"index": 1, "text_clean": "还不错"}])

        with patch("merism.conductor.llm_polish.get_llm", return_value=fake):
            out = await polish_session_turns(turns)

        # System turn kept as-is + text_clean = text_raw (no polish, rule_clean doesn't touch English).
        assert out[0]["role"] == "system"
        assert out[0]["text_raw"] == "Session started"
        assert out[0]["text_clean"] == "Session started"
