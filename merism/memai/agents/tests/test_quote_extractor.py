"""Tests for :mod:`merism.memai.agents.quote_extractor`."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any
from unittest.mock import patch

import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model

from merism.memai.agents.quote_extractor import extract_quotes
from merism.models import (
    InterviewGuide,
    InterviewSession,
    Organization,
    Participant,
    Participation,
    SessionQuote,
    Study,
    Team,
)


# ── Fake LLM ──

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
        return _FakeCompletion(
            choices=[_FakeChoice(message=_FakeMessage(content=self.body))]
        )


class _FakeChat:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.completions = completions


class _FakeClient:
    def __init__(self, body: str) -> None:
        self.chat = _FakeChat(_FakeCompletions(body))


# ── Fixtures ──

@sync_to_async
def _make_session(suffix: str) -> InterviewSession:
    User = get_user_model()
    user = User.objects.create_superuser(
        username=f"qe-{suffix}@m.test", email=f"qe-{suffix}@m.test", password="x"
    )
    org = Organization.objects.create(name=f"Org {suffix}", slug=f"qe-{suffix}")
    team = Team.objects.create(name="QE", organization=org)
    study = Study.objects.create(
        team=team,
        created_by=user,
        research_goal="Why do users churn at day 14?",
    )
    guide = InterviewGuide.objects.create(
        team=team, study=study, version="1.0.0", is_current=True, sections=[]
    )
    participant = Participant.objects.create(team=team, external_id=f"p-{suffix}")
    participation = Participation.objects.create(
        team=team, study=study, participant=participant
    )
    return InterviewSession.objects.create(
        team=team,
        study=study,
        guide=guide,
        participation=participation,
    )


# ── Tests ──

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_extracts_from_clean_transcript():
    session = await _make_session("happy")
    session.transcript = [
        {"ts": 1.0, "role": "agent", "text_clean": "欢迎。"},
        {
            "ts": 5.0,
            "role": "participant",
            "text_clean": "我觉得定价太贵了，每月 80 元不值。",
            "question_id": "q1",
        },
        {"ts": 30.0, "role": "agent", "text_clean": "能说说为什么吗？"},
        {
            "ts": 35.0,
            "role": "participant",
            "text_clean": "因为和竞品比功能少了一半。",
            "question_id": "q1",
        },
    ]
    await sync_to_async(session.save)(update_fields=["transcript"])

    body = json.dumps(
        {
            "quotes": [
                {
                    "turn_ref": 0,
                    "text": "我觉得定价太贵了，每月 80 元不值。",
                    "importance": 0.85,
                    "reason": "pricing_complaint",
                },
                {
                    "turn_ref": 1,
                    "text": "因为和竞品比功能少了一半。",
                    "importance": 0.75,
                    "reason": "competitor_gap",
                },
            ]
        }
    )

    with patch(
        "merism.memai.agents.quote_extractor.get_llm", return_value=_FakeClient(body)
    ):
        rows = await extract_quotes(session)

    assert len(rows) == 2
    assert rows[0].text.startswith("我觉得定价太贵")
    assert rows[0].importance == 0.85
    assert rows[0].question_id == "q1"
    assert rows[0].turn_indices == [1]  # original index 1, agent is 0
    assert rows[1].turn_indices == [3]
    assert rows[0].tags == {"extractor_reason": "pricing_complaint"}


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_idempotent_when_quotes_exist():
    session = await _make_session("idem")

    # Pre-seed one quote.
    await sync_to_async(SessionQuote.objects.create)(
        team=session.team,
        study=session.study,
        session=session,
        text="existing",
        importance=0.5,
    )
    session.transcript = [{"ts": 1.0, "role": "participant", "text_clean": "new content"}]
    await sync_to_async(session.save)(update_fields=["transcript"])

    called = {"n": 0}

    class _CountingCompletions:
        async def create(self, **kwargs: Any) -> Any:
            called["n"] += 1
            return _FakeCompletion(choices=[_FakeChoice(_FakeMessage("{\"quotes\":[]}"))])

    fake = _FakeClient("")
    fake.chat.completions = _CountingCompletions()  # type: ignore[assignment]

    with patch("merism.memai.agents.quote_extractor.get_llm", return_value=fake):
        rows = await extract_quotes(session)

    # Returns existing row, doesn't call LLM.
    assert len(rows) == 1
    assert called["n"] == 0


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_no_participant_turns_returns_empty():
    session = await _make_session("empty")
    session.transcript = [
        {"ts": 1.0, "role": "agent", "text_clean": "only agent turns"},
    ]
    await sync_to_async(session.save)(update_fields=["transcript"])

    rows = await extract_quotes(session)
    assert rows == []


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_llm_failure_returns_empty():
    session = await _make_session("fail")
    session.transcript = [
        {"ts": 1.0, "role": "participant", "text_clean": "something useful"},
    ]
    await sync_to_async(session.save)(update_fields=["transcript"])

    class _ExplodingCompletions:
        async def create(self, **kwargs: Any) -> Any:
            raise RuntimeError("boom")

    fake = _FakeClient("")
    fake.chat.completions = _ExplodingCompletions()  # type: ignore[assignment]

    with patch("merism.memai.agents.quote_extractor.get_llm", return_value=fake):
        rows = await extract_quotes(session)

    assert rows == []
    # No rows persisted.
    existing = await sync_to_async(lambda: list(SessionQuote.objects.filter(session=session)))()
    assert existing == []


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_turn_ref_out_of_range_skipped():
    session = await _make_session("oob")
    session.transcript = [
        {"ts": 1.0, "role": "participant", "text_clean": "only one turn"},
    ]
    await sync_to_async(session.save)(update_fields=["transcript"])

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
    ):
        rows = await extract_quotes(session)

    # Only the valid turn_ref is persisted.
    assert len(rows) == 1
    assert rows[0].text == "only one turn"
