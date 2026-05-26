"""Tests for :mod:`merism.memai.agents.quote_tagger`."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import patch

import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model

from merism.memai.agents.quote_tagger import (
    promote_inductive_suggestions,
    tag_quote,
)
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
def _make_quote_and_study(suffix: str) -> tuple[SessionQuote, Study]:
    User = get_user_model()
    user = User.objects.create_superuser(
        username=f"qt-{suffix}@m.test", email=f"qt-{suffix}@m.test", password="x"
    )
    org = Organization.objects.create(name=f"Org {suffix}", slug=f"qt-{suffix}")
    team = Team.objects.create(name="QT", organization=org)
    study = Study.objects.create(
        team=team,
        created_by=user,
        research_goal="x",
        codebook=[
            {
                "code_id": "pricing_complaint",
                "name": "Pricing Complaint",
                "description": "Expensive / not worth it",
                "examples": ["too expensive"],
                "source": "seeded",
            },
            {
                "code_id": "positive_sentiment",
                "name": "Positive Sentiment",
                "description": "Clear approval",
                "examples": ["love it"],
                "source": "seeded",
            },
        ],
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
    quote = SessionQuote.objects.create(
        team=team,
        study=study,
        session=session,
        text="太贵了，每月 80 块不值",
        importance=0.8,
    )
    return quote, study


# ── Tests ──

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_tags_with_deductive_and_inductive():
    quote, study = await _make_quote_and_study("happy")
    body = json.dumps(
        {
            "deductive": [{"code_id": "pricing_complaint", "confidence": 0.9}],
            "inductive_suggestions": [
                {"code": "value_for_money", "rationale": "Specific cost-benefit objection"}
            ],
            "sentiment": "negative",
            "action_type": "complaint",
        }
    )
    with (
        patch("merism.llm_gateway.client.get_client", return_value=None),
        patch("merism.memai.agents.quote_tagger.get_llm", return_value=_FakeClient(body)),
    ):
        tags = await tag_quote(quote, study)

    assert tags["sentiment"] == "negative"
    assert tags["action_type"] == "complaint"
    assert len(tags["deductive"]) == 1
    assert tags["deductive"][0]["code_id"] == "pricing_complaint"
    assert len(tags["inductive_suggestions"]) == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_unknown_deductive_code_filtered_out():
    quote, study = await _make_quote_and_study("unknown")
    # LLM hallucinates a code not in the codebook.
    body = json.dumps(
        {
            "deductive": [
                {"code_id": "pricing_complaint", "confidence": 0.8},
                {"code_id": "hallucinated_code", "confidence": 0.9},
            ],
            "inductive_suggestions": [],
            "sentiment": "negative",
            "action_type": None,
        }
    )
    with (
        patch("merism.llm_gateway.client.get_client", return_value=None),
        patch("merism.memai.agents.quote_tagger.get_llm", return_value=_FakeClient(body)),
    ):
        tags = await tag_quote(quote, study)

    # Only the known code survives.
    assert len(tags["deductive"]) == 1
    assert tags["deductive"][0]["code_id"] == "pricing_complaint"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_idempotent_when_already_tagged():
    quote, study = await _make_quote_and_study("idem")
    pre_tags = {
        "deductive": [{"code_id": "positive_sentiment", "confidence": 0.5}],
        "sentiment": "positive",
    }
    quote.tags = pre_tags
    await sync_to_async(quote.save)(update_fields=["tags"])

    called = {"n": 0}

    class _Counting:
        async def create(self, **kwargs: Any) -> Any:
            called["n"] += 1
            return _FakeCompletion(
                choices=[_FakeChoice(_FakeMessage('{"deductive":[],"inductive_suggestions":[],"sentiment":"neutral","action_type":null}'))]
            )

    fake = _FakeClient("")
    fake.chat.completions = _Counting()  # type: ignore[assignment]

    with patch("merism.llm_gateway.client.get_client", return_value=None), \
         patch("merism.memai.agents.quote_tagger.get_llm", return_value=fake):
        tags = await tag_quote(quote, study)

    assert called["n"] == 0
    assert tags == pre_tags


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_promote_inductive_suggestions_threshold():
    quote, study = await _make_quote_and_study("promote")
    # Simulate 3 quotes with same inductive suggestion.
    for i in range(3):
        await sync_to_async(SessionQuote.objects.create)(
            team=quote.team,
            study=quote.study,
            session=quote.session,
            text=f"q{i}",
            tags={
                "inductive_suggestions": [
                    {"code": "value_for_money", "rationale": "cost-benefit"}
                ]
            },
        )

    added = await promote_inductive_suggestions(study, min_occurrences=2)
    assert added == 1

    await sync_to_async(study.refresh_from_db)()
    code_ids = {c["code_id"] for c in study.codebook}
    assert "value_for_money" in code_ids


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_llm_failure_preserves_existing_tags():
    quote, study = await _make_quote_and_study("fail")
    quote.tags = {"extractor_reason": "pricing"}
    await sync_to_async(quote.save)(update_fields=["tags"])

    class _Exploding:
        async def create(self, **kwargs: Any) -> Any:
            raise RuntimeError("boom")

    fake = _FakeClient("")
    fake.chat.completions = _Exploding()  # type: ignore[assignment]

    with patch("merism.llm_gateway.client.get_client", return_value=None), \
         patch("merism.memai.agents.quote_tagger.get_llm", return_value=fake):
        tags = await tag_quote(quote, study)

    # Existing tag preserved, no deductive key added.
    assert tags == {"extractor_reason": "pricing"}
