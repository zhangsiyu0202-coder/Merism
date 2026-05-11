"""Tests for :mod:`merism.memai.agents.session_insight_generator`.

The generator now runs a LangGraph multi-node agent. Tests patch
``merism.memai.graph.call_llm_json`` which is the single seam every
node hits, letting us return canned JSON per node call.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

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


@sync_to_async
def _make_session_with_quotes(
    suffix: str, count: int = 3
) -> tuple[InterviewSession, list[SessionQuote]]:
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


def _llm_responses_happy(quote_ids: list[str]) -> list[dict[str, Any]]:
    """Build the sequence of JSON responses for each node in the graph.

    Order: plan → extract_tasks → compose_summary  (validate is pure Python)
    """
    return [
        # plan_node
        {"highlight_quote_ids": [quote_ids[0], quote_ids[2]]},
        # extract_tasks_node
        {
            "tasks": [
                {
                    "title": "Reconsider pricing tiers",
                    "category": "pricing",
                    "priority": "p0",
                    "evidence_quote_id": quote_ids[0],
                }
            ]
        },
        # compose_summary_node
        {
            "summary": (
                "The participant expressed frustration with pricing "
                "and praised the UI during the session."
            )
        },
    ]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_generates_insight_happy_path():
    session, quotes = await _make_session_with_quotes("happy", count=3)
    quote_ids = [str(q.id) for q in quotes]

    responses = _llm_responses_happy(quote_ids)
    mock = AsyncMock(side_effect=responses)

    with patch(
        "merism.memai.agents.session_insight_generator.call_llm_json",
        mock,
    ):
        insight = await generate_insight(session, quotes)

    assert insight is not None
    assert "frustration" in insight.summary
    assert len(insight.highlights) == 2
    assert insight.highlights[0]["quote_id"] == quote_ids[0]
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

    mock = AsyncMock()
    with patch(
        "merism.memai.agents.session_insight_generator.call_llm_json",
        mock,
    ):
        insight = await generate_insight(session, quotes)

    # Existing insight returned without ANY LLM call
    assert mock.call_count == 0
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
async def test_graph_failure_returns_none():
    session, quotes = await _make_session_with_quotes("fail", count=1)

    mock = AsyncMock(side_effect=RuntimeError("boom"))
    with patch(
        "merism.memai.agents.session_insight_generator.call_llm_json",
        mock,
    ):
        insight = await generate_insight(session, quotes)

    assert insight is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_fallback_highlights_when_llm_omits():
    session, quotes = await _make_session_with_quotes("fallback", count=3)

    # plan returns no highlights → extract_tasks early-returns without LLM call
    # → compose_summary still runs
    responses = [
        {"highlight_quote_ids": []},  # plan
        {"summary": "Short but valid summary for this test of fallback logic."},  # compose_summary
    ]
    mock = AsyncMock(side_effect=responses)

    with patch(
        "merism.memai.agents.session_insight_generator.call_llm_json",
        mock,
    ):
        insight = await generate_insight(session, quotes)

    # Falls back to top 3 by importance
    assert insight is not None
    assert len(insight.highlights) == 3
    assert insight.highlights[0]["quote_id"] == str(quotes[2].id)
