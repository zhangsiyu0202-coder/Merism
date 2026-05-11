"""Tests for :mod:`merism.memai.agents.codebook_seeder`."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import patch

import pytest
from asgiref.sync import sync_to_async

from merism.memai.agents.codebook_seeder import seed_codebook
from merism.models import Organization, Study, Team


# ── Fake LLM shape ──

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


# ── Helpers ──

@sync_to_async
def _make_team(slug: str = "test-codebook") -> Team:
    org = Organization.objects.create(name=f"Org {slug}", slug=slug)
    return Team.objects.create(name="Test", organization=org)


@sync_to_async
def _make_study(team: Team, **kwargs: Any) -> Study:
    return Study.objects.create(team=team, **kwargs)


# ── Tests ──

_SEED_RESPONSE = json.dumps(
    {
        "codes": [
            {
                "code_id": "pricing_complaint",
                "name": "Pricing Complaint",
                "description": "Participant calls the product expensive or not worth it.",
                "examples": ["too expensive", "not worth the money"],
            },
            {
                "code_id": "positive_sentiment",
                "name": "Positive Sentiment",
                "description": "Any clearly positive affect.",
                "examples": ["I love it"],
            },
            {
                "code_id": "onboarding_friction",
                "name": "Onboarding Friction",
                "description": "Describes a point of confusion during first use.",
                "examples": ["I didn't know where to click"],
            },
        ]
    }
)


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_seeds_from_research_goal_and_objectives():
    team = await _make_team("seed-happy")
    study = await _make_study(
        team,
        research_goal="Why do users churn at day 14?",
        research_objectives=["Map day-14 moments", "Find expectation gaps"],
    )
    fake = _FakeClient(_SEED_RESPONSE)

    with patch("merism.memai.agents.codebook_seeder.get_llm", return_value=fake):
        codes = await seed_codebook(study)

    assert len(codes) == 3
    assert all(c["source"] == "seeded" for c in codes)
    assert codes[0]["code_id"] == "pricing_complaint"

    await sync_to_async(study.refresh_from_db)()
    assert len(study.codebook) == 3


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_existing_codebook_preserved():
    team = await _make_team("seed-exists")
    existing = [
        {
            "code_id": "custom",
            "name": "Custom",
            "description": "...",
            "examples": [],
            "source": "manual",
        }
    ]
    study = await _make_study(
        team,
        research_goal="x",
        research_objectives=["y"],
        codebook=existing,
    )
    fake = _FakeClient(_SEED_RESPONSE)

    with patch("merism.memai.agents.codebook_seeder.get_llm", return_value=fake):
        codes = await seed_codebook(study)

    # LLM not called, returns existing.
    assert codes == existing


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_empty_study_returns_empty():
    team = await _make_team("seed-empty")
    study = await _make_study(team, research_goal="", research_objectives=[])
    codes = await seed_codebook(study)
    assert codes == []


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_llm_failure_returns_empty():
    team = await _make_team("seed-fail")
    study = await _make_study(team, research_goal="x", research_objectives=["y"])

    class _ExplodingCompletions:
        async def create(self, **kwargs: Any) -> Any:
            raise RuntimeError("boom")

    fake = _FakeClient("")
    fake.chat.completions = _ExplodingCompletions()  # type: ignore[assignment]

    with patch("merism.memai.agents.codebook_seeder.get_llm", return_value=fake):
        codes = await seed_codebook(study)

    assert codes == []
    await sync_to_async(study.refresh_from_db)()
    assert study.codebook == []
