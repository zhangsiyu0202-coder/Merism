"""finalize_to_session — bridge graph terminal state into InterviewSession row."""
# pyright: reportTypedDictNotRequiredAccess=false

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import patch

import pytest

from merism.conductor.persistence import finalize_to_session


class _FakeGraphState:
    def __init__(self, values: dict[str, Any] | None) -> None:
        self.values = values or {}


class _FakeGraph:
    """Stand-in for a CompiledStateGraph; only ``aget_state`` is exercised."""

    def __init__(self, state_values: dict[str, Any] | None) -> None:
        self._state = _FakeGraphState(state_values) if state_values is not None else None

    async def aget_state(self, config: Any) -> Any:
        return self._state


@pytest.fixture
def session_factory(db):
    """Build a real InterviewSession row in ACTIVE status."""
    from django.contrib.auth import get_user_model

    from merism.models import (
        InterviewGuide,
        InterviewSession,
        Organization,
        Participant,
        Participation,
        Study,
        Team,
    )

    User = get_user_model()

    def _build(
        *,
        status: str = InterviewSession.Status.ACTIVE,
    ) -> InterviewSession:
        suffix = uuid.uuid4().hex[:8]
        admin = User.objects.create_superuser(
            username=f"v3test-{suffix}@merism.test",
            email=f"v3test-{suffix}@merism.test",
            password="x",
        )
        org = Organization.objects.create(name=f"Org {suffix}", slug=f"org-{suffix}")
        team = Team.objects.create(name="R", organization=org)
        study = Study.objects.create(
            team=team,
            created_by=admin,
            name="V3 Persistence Test",
            research_goal="Test finalize_to_session",
            interview_mode=Study.InterviewMode.TEXT,
            estimated_minutes=10,
        )
        guide = InterviewGuide.objects.create(
            team=team,
            study=study,
            version="3.0.0",
            is_current=True,
            sections={"version": "v3", "sections": []},
        )
        participant = Participant.objects.create(team=team, external_id=f"v3p-{suffix}", name="V3 Tester")
        participation = Participation.objects.create(team=team, study=study, participant=participant)
        return InterviewSession.objects.create(
            team=team,
            study=study,
            guide=guide,
            participation=participation,
            status=status,
        )

    return _build


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestFinalizeToSession:
    async def test_writes_transcript(self, session_factory: Any) -> None:
        from merism.models import InterviewSession

        session = await self._mk_session(session_factory)
        graph = _FakeGraph(
            {
                "done": True,
                "transcript": [
                    {
                        "section_id": "s1",
                        "question_id": "q1",
                        "kind": "main",
                        "question": "Q?",
                        "answer": "A.",
                    }
                ],
            }
        )

        ok = await finalize_to_session(graph, str(session.id))
        assert ok is True

        await self._refresh(session)
        assert session.status == InterviewSession.Status.COMPLETED
        # v3 turn → 2 v1-compat entries (agent + participant)
        assert len(session.transcript) == 2
        assert session.transcript[0]["role"] == "agent"
        assert session.transcript[0]["text"] == "Q?"
        assert session.transcript[0]["question_id"] == "q1"
        assert session.transcript[0]["kind"] == "main"
        assert session.transcript[1]["role"] == "participant"
        assert session.transcript[1]["text"] == "A."
        assert session.transcript[1]["question_id"] == "q1"
        # Original v3-shape preserved on moderator_state for v3-aware analytics
        assert len(session.moderator_state["v3_transcript"]) == 1
        assert session.moderator_state["v3_transcript"][0]["question_id"] == "q1"
        assert session.moderator_state["engine"] == "v3"
        assert "final_report" not in session.moderator_state

    async def test_skips_when_graph_not_done(self, session_factory: Any) -> None:
        session = await self._mk_session(session_factory)
        graph = _FakeGraph({"done": False, "transcript": []})

        ok = await finalize_to_session(graph, str(session.id))
        assert ok is False

        from merism.models import InterviewSession

        await self._refresh(session)
        assert session.status != InterviewSession.Status.COMPLETED

    async def test_skips_when_no_state(self, session_factory: Any) -> None:
        session = await self._mk_session(session_factory)
        graph = _FakeGraph(None)

        ok = await finalize_to_session(graph, str(session.id))
        assert ok is False

    async def test_idempotent_when_already_completed(self, session_factory: Any) -> None:
        from merism.models import InterviewSession

        session = await self._mk_session(session_factory, status=InterviewSession.Status.COMPLETED)
        graph = _FakeGraph(
            {
                "done": True,
                "transcript": [
                    {"section_id": "s1", "question_id": "q1", "kind": "main", "question": "Q?", "answer": "A."}
                ],
            }
        )

        ok = await finalize_to_session(graph, str(session.id))
        assert ok is False  # 0 rows updated due to .exclude(status="completed")

        await self._refresh(session)
        # Original (empty) state preserved
        assert session.transcript == []
        assert session.moderator_state == {}

    async def test_records_last_error_when_present(self, session_factory: Any) -> None:
        session = await self._mk_session(session_factory)
        graph = _FakeGraph(
            {
                "done": True,
                "transcript": [],
                "last_error": "judge_call_failed",
            }
        )

        ok = await finalize_to_session(graph, str(session.id))
        assert ok is True

        await self._refresh(session)
        assert session.moderator_state["last_error"] == "judge_call_failed"

    async def test_saves_through_model_save_and_triggers_signals(
        self, session_factory: Any
    ) -> None:
        from merism.models import InboxItem, InterviewSession

        session = await self._mk_session(session_factory)
        graph = _FakeGraph(
            {
                "done": True,
                "transcript": [
                    {
                        "section_id": "s1",
                        "question_id": "q1",
                        "kind": "main",
                        "question": "Q?",
                        "answer": "A.",
                    }
                ],
            }
        )

        with (
            patch("merism.conductor.tasks.process_completed_session.delay") as process_completed_session_delay,
            patch("merism.knowledge.tasks.index_transcript_task.delay") as index_transcript_delay,
        ):
            ok = await finalize_to_session(graph, str(session.id))

        assert ok is True

        assert process_completed_session_delay.called is True
        assert index_transcript_delay.called is True

        await self._refresh(session)
        assert session.status == InterviewSession.Status.COMPLETED
        assert await InboxItem.objects.filter(
            team_id=session.team_id,
            kind="session_completed",
            ref_kind="session",
            ref_id=str(session.id),
        ).aexists()

    # ── Helpers ──

    @staticmethod
    async def _mk_session(factory: Any, **kwargs: Any) -> Any:
        from asgiref.sync import sync_to_async

        return await sync_to_async(factory)(**kwargs)

    @staticmethod
    async def _refresh(session: Any) -> None:
        from asgiref.sync import sync_to_async

        await sync_to_async(session.refresh_from_db)()
