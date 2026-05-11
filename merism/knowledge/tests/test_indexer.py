"""Tests for :mod:`merism.knowledge.indexer`."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model

from merism.knowledge.indexer import index_session_quotes
from merism.models import (
    InterviewGuide,
    InterviewSession,
    KnowledgeChunk,
    KnowledgeDocument,
    Organization,
    Participant,
    Participation,
    SessionQuote,
    Study,
    Team,
)


@sync_to_async
def _make_session_with_quotes(suffix: str, count: int = 3) -> tuple[InterviewSession, list[SessionQuote]]:
    User = get_user_model()
    user = User.objects.create_superuser(
        username=f"idx-{suffix}@m.test", email=f"idx-{suffix}@m.test", password="x"
    )
    org = Organization.objects.create(name=f"Org {suffix}", slug=f"idx-{suffix}")
    team = Team.objects.create(name="IDX", organization=org)
    study = Study.objects.create(team=team, created_by=user, research_goal="x")
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
            text=f"quote text {i}",
            importance=0.5,
        )
        for i in range(count)
    ]
    return session, quotes


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_indexes_quotes_creates_chunks():
    session, quotes = await _make_session_with_quotes("ok", count=3)

    # Fake embed_batch returns 1536-long zero vectors.
    fake_embedding = [0.0] * 1536

    with patch(
        "merism.knowledge.indexer.embed_batch",
        return_value=[fake_embedding] * 3,
    ):
        written = await index_session_quotes(session, quotes)

    assert written == 3

    # Document created with the right source_type.
    doc = await sync_to_async(KnowledgeDocument.objects.get)(
        session=session, source_type=KnowledgeDocument.SourceType.SESSION_INSIGHT
    )
    assert doc.title.startswith("Session ")

    chunks = await sync_to_async(list)(KnowledgeChunk.objects.filter(document=doc))
    assert len(chunks) == 3
    assert chunks[0].metadata["quote_id"] == str(quotes[0].id)
    assert chunks[0].metadata["study_id"] == str(session.study_id)

    # Quotes marked embedded.
    await sync_to_async(quotes[0].refresh_from_db)()
    assert quotes[0].embedded_at is not None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_idempotent_when_already_embedded():
    session, quotes = await _make_session_with_quotes("idem", count=2)

    # Pre-mark all quotes as embedded.
    from django.utils import timezone

    now = timezone.now()
    await sync_to_async(SessionQuote.objects.filter(session=session).update)(
        embedded_at=now
    )
    # Refresh Python objects so they reflect the DB update.
    for q in quotes:
        await sync_to_async(q.refresh_from_db)()

    called = {"n": 0}

    def _counting(texts):
        called["n"] += 1
        return [[0.0] * 1536] * len(texts)

    with patch("merism.knowledge.indexer.embed_batch", side_effect=_counting):
        written = await index_session_quotes(session, quotes)

    # No embedding calls, no chunks written.
    assert called["n"] == 0
    assert written == 0


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_embedding_failure_skips_quote():
    session, quotes = await _make_session_with_quotes("fail", count=2)

    # First quote embeds OK, second returns None (failure).
    with patch(
        "merism.knowledge.indexer.embed_batch",
        return_value=[[0.0] * 1536, None],
    ):
        written = await index_session_quotes(session, quotes)

    assert written == 1

    # Only one chunk row.
    chunks = await sync_to_async(list)(KnowledgeChunk.objects.filter(team=session.team))
    assert len(chunks) == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_empty_input_is_noop():
    session, _ = await _make_session_with_quotes("empty", count=0)
    written = await index_session_quotes(session, [])
    assert written == 0
