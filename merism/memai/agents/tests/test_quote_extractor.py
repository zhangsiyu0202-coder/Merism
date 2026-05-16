"""Tests for :mod:`merism.memai.agents.quote_extractor`."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from merism.memai.agents.quote_extractor import extract_quotes


@dataclass
class _FakeMessage:
    content: str


@dataclass
class _FakeChoice:
    message: _FakeMessage


@dataclass
class _FakeCompletion:
    choices: list[_FakeChoice]


class _FakeCompletions:
    def __init__(self, body: str) -> None:
        self.body = body

    async def create(self, **kwargs: Any) -> _FakeCompletion:
        return _FakeCompletion(choices=[_FakeChoice(message=_FakeMessage(content=self.body))])


class _FakeChat:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.completions = completions


class _FakeClient:
    def __init__(self, body: str) -> None:
        self.chat = _FakeChat(_FakeCompletions(body))


@pytest.fixture(autouse=True)
def _disable_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_gateway(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr("merism.llm_gateway.client.get_client", _no_gateway)


def _make_session() -> SimpleNamespace:
    team = SimpleNamespace(id=uuid.uuid4(), name="Team")
    study = SimpleNamespace(id=uuid.uuid4(), team=team)
    return SimpleNamespace(
        id=uuid.uuid4(),
        team=team,
        study=study,
        trace_id=uuid.uuid4(),
        transcript=[],
    )


async def _fake_persist_quotes(
    session: SimpleNamespace,
    quotes: list[Any],
    participant_turns: list[tuple[int, dict[str, Any]]],
    full_transcript: list[dict[str, Any]],
) -> list[SimpleNamespace]:
    rows: list[SimpleNamespace] = []
    for q in quotes:
        if q.turn_ref >= len(participant_turns):
            continue
        orig_idx, turn = participant_turns[q.turn_ref]
        ts_start_ms = int(float(turn.get("ts") or 0.0) * 1000)
        next_turn = full_transcript[orig_idx + 1] if orig_idx + 1 < len(full_transcript) else None
        ts_end_ms = int(float(next_turn.get("ts") or 0.0) * 1000) if next_turn else ts_start_ms + 5000
        rows.append(
            SimpleNamespace(
                team=session.team,
                study=session.study,
                session=session,
                text=q.text.strip(),
                turn_indices=[orig_idx],
                ts_start_ms=ts_start_ms,
                ts_end_ms=max(ts_end_ms, ts_start_ms + 500),
                question_id=str(turn.get("question_id") or ""),
                concept_id=str(turn.get("concept_id") or ""),
                importance=q.importance,
                tags={"extractor_reason": q.reason} if q.reason else {},
            )
        )
    return rows


@pytest.mark.asyncio
async def test_extracts_from_clean_transcript() -> None:
    session = _make_session()
    session.transcript = [
        {"ts": 1.0, "role": "agent", "text_clean": "欢迎。"},
        {
            "ts": 5.0,
            "role": "participant",
            "text_clean": "我觉得定价太贵了,每月 80 元不值.",
            "question_id": "q1",
        },
        {"ts": 30.0, "role": "agent", "text_clean": "能说说为什么吗?"},
        {
            "ts": 35.0,
            "role": "participant",
            "text_clean": "因为和竞品比功能少了一半.",
            "question_id": "q1",
        },
    ]
    body = json.dumps(
        {
            "quotes": [
                {
                    "turn_ref": 0,
                    "text": "我觉得定价太贵了,每月 80 元不值.",
                    "importance": 0.85,
                    "reason": "pricing_complaint",
                },
                {
                    "turn_ref": 1,
                    "text": "因为和竞品比功能少了一半.",
                    "importance": 0.75,
                    "reason": "competitor_gap",
                },
            ]
        }
    )

    with patch(
        "merism.memai.agents.quote_extractor.get_llm", return_value=_FakeClient(body)
    ), patch("merism.memai.agents.quote_extractor._aget_existing_quotes", return_value=[]), patch(
        "merism.memai.agents.quote_extractor._persist_quotes", side_effect=_fake_persist_quotes
    ):
        rows = await extract_quotes(session)  # type: ignore[arg-type]

    assert len(rows) == 2
    assert rows[0].text.startswith("我觉得定价太贵")
    assert rows[0].importance == 0.85
    assert rows[0].question_id == "q1"
    assert rows[0].turn_indices == [1]
    assert rows[1].turn_indices == [3]
    assert rows[0].tags == {"extractor_reason": "pricing_complaint"}


@pytest.mark.asyncio
async def test_extracts_from_user_assistant_aliases() -> None:
    session = _make_session()
    session.transcript = [
        {"ts": 1.0, "role": "assistant", "text_clean": "欢迎。"},
        {
            "ts": 5.0,
            "role": "user",
            "text_clean": "我觉得定价太贵了,每月 80 元不值.",
            "question_id": "q1",
        },
    ]
    body = json.dumps(
        {
            "quotes": [
                {
                    "turn_ref": 0,
                    "text": "我觉得定价太贵了,每月 80 元不值.",
                    "importance": 0.85,
                    "reason": "pricing_complaint",
                }
            ]
        }
    )

    with patch(
        "merism.memai.agents.quote_extractor.get_llm", return_value=_FakeClient(body)
    ), patch("merism.memai.agents.quote_extractor._aget_existing_quotes", return_value=[]), patch(
        "merism.memai.agents.quote_extractor._persist_quotes", side_effect=_fake_persist_quotes
    ):
        rows = await extract_quotes(session)  # type: ignore[arg-type]

    assert len(rows) == 1
    assert rows[0].turn_indices == [1]


@pytest.mark.asyncio
async def test_idempotent_when_quotes_exist() -> None:
    session = _make_session()
    session.transcript = [{"ts": 1.0, "role": "participant", "text_clean": "new content"}]
    existing = [SimpleNamespace(text="existing")]

    called = {"n": 0}

    class _CountingCompletions:
        async def create(self, **kwargs: Any) -> Any:
            called["n"] += 1
            return _FakeCompletion(choices=[_FakeChoice(_FakeMessage("{\"quotes\":[]}"))])

    fake = _FakeClient("")
    fake.chat.completions = _CountingCompletions()  # type: ignore[assignment]

    with patch("merism.memai.agents.quote_extractor.get_llm", return_value=fake), patch(
        "merism.memai.agents.quote_extractor._aget_existing_quotes", return_value=existing
    ):
        rows = await extract_quotes(session)  # type: ignore[arg-type]

    assert len(rows) == 1
    assert called["n"] == 0


@pytest.mark.asyncio
async def test_no_participant_turns_returns_empty() -> None:
    session = _make_session()
    session.transcript = [{"ts": 1.0, "role": "agent", "text_clean": "only agent turns"}]

    with patch("merism.memai.agents.quote_extractor._aget_existing_quotes", return_value=[]):
        rows = await extract_quotes(session)  # type: ignore[arg-type]
    assert rows == []


@pytest.mark.asyncio
async def test_llm_failure_returns_empty() -> None:
    session = _make_session()
    session.transcript = [{"ts": 1.0, "role": "participant", "text_clean": "something useful"}]

    class _ExplodingCompletions:
        async def create(self, **kwargs: Any) -> Any:
            raise RuntimeError("boom")

    fake = _FakeClient("")
    fake.chat.completions = _ExplodingCompletions()  # type: ignore[assignment]

    with patch("merism.memai.agents.quote_extractor.get_llm", return_value=fake), patch(
        "merism.memai.agents.quote_extractor._aget_existing_quotes", return_value=[]
    ):
        rows = await extract_quotes(session)  # type: ignore[arg-type]

    assert rows == []


@pytest.mark.asyncio
async def test_turn_ref_out_of_range_skipped() -> None:
    session = _make_session()
    session.transcript = [{"ts": 1.0, "role": "participant", "text_clean": "only one turn"}]
    body = json.dumps(
        {
            "quotes": [
                {"turn_ref": 0, "text": "only one turn", "importance": 0.5, "reason": ""},
                {"turn_ref": 99, "text": "hallucinated", "importance": 0.5, "reason": ""},
            ]
        }
    )
    with patch(
        "merism.memai.agents.quote_extractor.get_llm", return_value=_FakeClient(body)
    ), patch("merism.memai.agents.quote_extractor._aget_existing_quotes", return_value=[]), patch(
        "merism.memai.agents.quote_extractor._persist_quotes", side_effect=_fake_persist_quotes
    ):
        rows = await extract_quotes(session)  # type: ignore[arg-type]

    assert len(rows) == 1
    assert rows[0].text == "only one turn"
