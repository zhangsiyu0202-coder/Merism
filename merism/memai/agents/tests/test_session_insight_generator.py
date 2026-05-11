"""Tests for :mod:`merism.memai.agents.session_insight_generator`."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import patch

import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model

from merism.memai.agents.session_insight_generator import generate_insight
from merism.models import (
    InterviewGuide,
    InterviewSession,
    Organization,
    Participant,
    Participation,
    SessionInsight,
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


@sync_to_async
def _make_session_with_quotes(suffix: str, count: int = 3) -> tuple[InterviewSession, list[SessionQuote]]:
    User = get_user_model()
    user = User.objects.create_superuser(
        username=f"si-{suffix}@m.test", email=f"si-{suffix}@m.test", password="x"
    )
    org = Organization.objects.create(name=f"Org {suffix}", slug=f"si-{suffix}")
    team = Team.objects.create(name="SI", organization=org)
    study = Study.objects.create(
        team=team, created_by=user, research_goal="Why do users churn?"
    )
    guide = InterviewGuide.objects.create(
        team=team, study=study, version="1.0.0", is_current=True, sections=[]
    )
    participant = Participant.objects.create(team=team, external_id=f"p-{suffix}")
    participation = Participation.objects.create(
        team=team, study=study, participant=participant
    )
    session = InterviewSession.objects.create(
        team=team, study=study, guide=guide, participation=participation
    )
    quotes = [
        SessionQuote.objects.create(
            team=team,
            study=study,
            session=session,
            text=f"quote {i} — something meaningful",
            importance=0.5 + i * 0.1,
            tags={
                "sentiment": "negative" if i % 2 == 0 else "positive",
                "action_type": "complaint" if i % 2 == 0 else None,
            },
        )
        for i in range(count)
    ]
    return session, quotes


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_generates_insight_happy_path():
    session, quotes = await _make_session_with_quotes("happy", count=3)

    body = json.dumps(
        {
            "summary": "The participant expressed frustration with pricing and praised the UI.",
            "highlight_quote_ids": [str(quotes[0].id), str(quotes[2].id)],
            "extracted_tasks": [
                {
                    "title": "Reconsider pricing tiers",
                    "category": "pricing",
                    "priority": "P0",
                    "evidence_quote_id": str(quotes[0].id),
                }
            ],
        }
    )
    with patch(
        "merism.memai.agents.session_insight_generator.get_llm",
        return_value=_FakeClient(body),
    ):
        insight = await generate_insight(session, quotes)

    assert insight is not None
    assert insight.summary.startswith("The participant expressed")
    assert len(insight.highlights) == 2
    assert insight.highlights[0]["quote_id"] == str(quotes[0].id)
    assert insight.tags["sentiment_counts"]["negative"] == 2
    assert insight.tags["quote_count"] == 3
    assert insight.extracted_tasks[0]["title"] == "Reconsider pricing tiers"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_idempotent_when_insight_exists():
    session, quotes = await _make_session_with_quotes("idem", count=2)

    existing = await sync_to_async(SessionInsight.objects.create)(
        team=session.team,
        session=session,
        summary="existing",
    )

    called = {"n": 0}

    class _Counting:
        async def create(self, **kwargs: Any) -> Any:
            called["n"] += 1
            return _FakeCompletion(
                choices=[_FakeChoice(_FakeMessage('{"summary":"x","highlight_quote_ids":[],"extracted_tasks":[]}'))]
            )

    fake = _FakeClient("")
    fake.chat.completions = _Counting()  # type: ignore[assignment]

    with patch(
        "merism.memai.agents.session_insight_generator.get_llm", return_value=fake
    ):
        insight = await generate_insight(session, quotes)

    assert called["n"] == 0
    assert insight is not None
    assert insight.id == existing.id


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_no_quotes_returns_none():
    session, _ = await _make_session_with_quotes("empty", count=0)
    insight = await generate_insight(session, [])
    assert insight is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_llm_failure_returns_none():
    session, quotes = await _make_session_with_quotes("fail", count=1)

    class _Exploding:
        async def create(self, **kwargs: Any) -> Any:
            raise RuntimeError("boom")

    fake = _FakeClient("")
    fake.chat.completions = _Exploding()  # type: ignore[assignment]

    with patch(
        "merism.memai.agents.session_insight_generator.get_llm", return_value=fake
    ):
        insight = await generate_insight(session, quotes)

    assert insight is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_fallback_highlights_when_llm_omits():
    session, quotes = await _make_session_with_quotes("fallback", count=3)

    body = json.dumps(
        {
            "summary": "Short but valid summary.",  # >=10 chars
            "highlight_quote_ids": [],  # LLM didn't choose any
            "extracted_tasks": [],
        }
    )
    with patch(
        "merism.memai.agents.session_insight_generator.get_llm",
        return_value=_FakeClient(body),
    ):
        insight = await generate_insight(session, quotes)

    # Falls back to top 3 by importance.
    assert insight is not None
    assert len(insight.highlights) == 3
    # Highest importance first.
    assert insight.highlights[0]["quote_id"] == str(quotes[2].id)
