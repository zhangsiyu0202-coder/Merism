"""Interview-domain factories.

InterviewSession, InterviewGuide, Participation, Participant, and turns
(records of what was said in a session).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, Literal


TurnRole = Literal["agent", "participant", "system"]
InterviewState = Literal["warmup", "active", "closing", "ended"]


def make_participant(
    *,
    participant_id: str | None = None,
    email: str = "participant@merism.test",
    name: str = "Test Participant",
    attributes: dict[str, Any] | None = None,
    stub: bool = True,
) -> SimpleNamespace:
    """Build a Participant identity."""
    if not stub:
        raise NotImplementedError("make_participant(stub=False) requires Phase C1")
    return SimpleNamespace(
        id=participant_id or f"p-{uuid.uuid4().hex[:8]}",
        email=email,
        name=name,
        attributes=attributes or {},
    )


def make_participation(
    study: SimpleNamespace,
    *,
    participant: SimpleNamespace | None = None,
    source: str = "direct_link",
    status: str = "invited",
    is_preview: bool = False,
    delivery_id: str | None = None,
    stub: bool = True,
    **extra: Any,
) -> SimpleNamespace:
    """Build a Participation record (one attempt by one participant to take one study)."""
    if not stub:
        raise NotImplementedError("make_participation(stub=False) requires Phase C1")
    participant = participant or make_participant()
    return SimpleNamespace(
        id=uuid.uuid4(),
        pk=uuid.uuid4(),
        study=study,
        study_id=study.id,
        team_id=study.team_id,
        participant=participant,
        participant_id=participant.id,
        source=source,
        status=status,
        is_preview=is_preview,
        delivery_id=delivery_id,
        browser_token=uuid.uuid4(),
        **extra,
    )


def make_interview_guide(
    study: SimpleNamespace,
    *,
    sections: list[dict[str, Any]] | None = None,
    is_current: bool = True,
    version: str = "1.0.0",
    language: str = "en",
    stub: bool = True,
) -> SimpleNamespace:
    """Build an InterviewGuide."""
    if not stub:
        raise NotImplementedError("make_interview_guide(stub=False) requires Phase C1")
    return SimpleNamespace(
        id=uuid.uuid4(),
        pk=uuid.uuid4(),
        study=study,
        study_id=study.id,
        sections=sections or _default_guide_sections(),
        is_current=is_current,
        version=version,
        language=language,
    )


def make_interview(
    study: SimpleNamespace | None = None,
    *,
    state: InterviewState = "active",
    mode: Literal["voice", "video", "text", "offline"] = "voice",
    participation: SimpleNamespace | None = None,
    guide: SimpleNamespace | None = None,
    locale: str = "en",
    stub: bool = True,
    **extra: Any,
) -> SimpleNamespace:
    """Build an InterviewSession.

    If ``study`` is omitted, a default stub study is created. Same for
    ``participation`` and ``guide``.
    """
    if not stub:
        raise NotImplementedError("make_interview(stub=False) requires Phase C1")

    if study is None:
        # Avoid a circular import at module load: resolve lazily.
        from merism.testing.factories.study import make_study

        study = make_study(interview_mode=mode, stub=True)
    if participation is None:
        participation = make_participation(study, stub=True)
    if guide is None:
        guide = make_interview_guide(study, stub=True)

    interview_id = uuid.uuid4()
    turns: list[SimpleNamespace] = []
    return SimpleNamespace(
        id=interview_id,
        pk=interview_id,
        study=study,
        study_id=study.id,
        team_id=study.team_id,
        participation=participation,
        participation_id=participation.id,
        guide=guide,
        guide_id=guide.id,
        mode=mode,
        state=state,
        status=state,  # legacy alias seen in some code paths
        locale=locale,
        turns=turns,
        vision_frames=[],
        started_at=datetime.now(UTC),
        ended_at=None,
        **extra,
    )


def make_turn(
    interview: SimpleNamespace,
    *,
    role: TurnRole = "agent",
    content: str = "Hello!",
    seq: int | None = None,
    metadata: dict[str, Any] | None = None,
    stub: bool = True,
) -> SimpleNamespace:
    """Append a turn to ``interview.turns`` and return the turn record."""
    if not stub:
        raise NotImplementedError("make_turn(stub=False) requires Phase C1")
    turn_seq = seq if seq is not None else len(interview.turns) + 1
    turn = SimpleNamespace(
        id=uuid.uuid4(),
        interview=interview,
        interview_id=interview.id,
        role=role,
        content=content,
        seq=turn_seq,
        metadata=metadata or {},
        at=datetime.now(UTC),
    )
    interview.turns.append(turn)
    return turn


def _default_guide_sections() -> list[dict[str, Any]]:
    return [
        {
            "id": "s1",
            "title": "Warmup",
            "questions": [
                {"id": "q1", "text": "Can you tell me about your role?"},
            ],
        },
        {
            "id": "s2",
            "title": "Core",
            "questions": [
                {"id": "q2", "text": "What do you find most frustrating in the product?"},
            ],
        },
    ]
