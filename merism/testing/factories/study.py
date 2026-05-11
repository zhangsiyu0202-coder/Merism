"""Study-domain factories: Study, StudyGoal, StudyTrigger, StudyLink, StudyTemplate.

Today every factory returns a ``SimpleNamespace`` with the shape Merism code
reads. Phase C1 will add a ``stub=False`` path that writes a real DB row.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any


_DEFAULT_TEAM_ID = 1
_NEXT_ID_COUNTER: dict[str, int] = {}


def _next_id(kind: str) -> int:
    _NEXT_ID_COUNTER[kind] = _NEXT_ID_COUNTER.get(kind, 0) + 1
    return _NEXT_ID_COUNTER[kind]


def make_study(
    *,
    name: str = "Test Study",
    research_goal: str = "Understand why users bounce at signup",
    team_id: int = _DEFAULT_TEAM_ID,
    interview_mode: str = "voice",
    status: str = "draft",
    slug: str | None = None,
    stub: bool = True,
    **extra: Any,
) -> SimpleNamespace:
    """Build a Study. Stub mode today (``SimpleNamespace``); DB-backed in Phase C1.

    ``interview_mode`` corresponds to ``Study.InterviewMode`` choices:
    ``voice`` / ``video`` / ``text`` / ``offline`` (see
    ``products/studies/backend/models.py``).
    """
    if not stub:
        raise NotImplementedError(
            "make_study(stub=False) requires Phase C1 (merism.Team model). "
            "For now pass stub=True (default) and assert on the namespace."
        )

    study_id = uuid.uuid4()
    return SimpleNamespace(
        id=study_id,
        pk=study_id,
        name=name,
        research_goal=research_goal,
        team_id=team_id,
        interview_mode=interview_mode,
        status=status,
        slug=slug or f"study-{_next_id('study'):04x}",
        goals=_FakeRelated([]),
        stimuli=_FakeRelated([]),
        screeners=_FakeRelated([]),
        success_metrics={},
        is_draft=lambda: status == "draft",
        is_active=lambda: status == "active",
        **extra,
    )


def make_study_goal(
    study: SimpleNamespace,
    *,
    question: str,
    priority: str = "p0",
    coverage: float = 0.0,
    is_answered: bool = False,
    stub: bool = True,
) -> SimpleNamespace:
    """Build a StudyGoal and attach it to ``study.goals``.

    ``priority``: ``"p0"`` (must-answer) / ``"p1"`` / ``"p2"``.
    ``coverage``: ``0.0`` – ``1.0``, updated incrementally per session.
    """
    if not stub:
        raise NotImplementedError("make_study_goal(stub=False) requires Phase C1")

    goal = SimpleNamespace(
        id=uuid.uuid4(),
        pk=uuid.uuid4(),
        study=study,
        study_id=study.id,
        question=question,
        priority=priority,
        coverage=float(coverage),
        is_answered=is_answered,
    )
    study.goals.add(goal)
    return goal


def make_study_with_goals(
    *,
    name: str = "Test Study",
    research_goal: str = "Understand why users bounce at signup",
    goals: list[str | tuple[str, str]] | None = None,
    interview_mode: str = "voice",
    team_id: int = _DEFAULT_TEAM_ID,
    stub: bool = True,
    **extra: Any,
) -> SimpleNamespace:
    """Shortcut: Study + a flat list of goals.

    ``goals`` items are either ``"question string"`` (defaults to p0) or
    ``("p1", "question string")`` tuples.
    """
    study = make_study(
        name=name,
        research_goal=research_goal,
        interview_mode=interview_mode,
        team_id=team_id,
        stub=stub,
        **extra,
    )
    for item in goals or []:
        if isinstance(item, tuple):
            priority, question = item
        else:
            priority, question = "p0", item
        make_study_goal(study, question=question, priority=priority, stub=stub)
    return study


def make_study_link(
    study: SimpleNamespace,
    *,
    slug: str | None = None,
    is_active: bool = True,
    url_base: str = "https://merism.test",
    stub: bool = True,
) -> SimpleNamespace:
    """Build a StudyLink with a slug-based URL."""
    if not stub:
        raise NotImplementedError("make_study_link(stub=False) requires Phase C1")
    resolved_slug = slug or f"link-{_next_id('study_link'):04x}"
    return SimpleNamespace(
        id=uuid.uuid4(),
        pk=uuid.uuid4(),
        study=study,
        study_id=study.id,
        slug=resolved_slug,
        is_active=is_active,
        url_path=lambda s=resolved_slug: f"/s/{s}",
        url=f"{url_base}/s/{resolved_slug}",
    )


def make_study_trigger(
    study: SimpleNamespace,
    *,
    condition_type: str = "event",
    event_name: str = "user_signed_up",
    is_active: bool = True,
    stub: bool = True,
    **extra: Any,
) -> SimpleNamespace:
    """Build a StudyTrigger (recruitment-by-behavior trigger)."""
    if not stub:
        raise NotImplementedError("make_study_trigger(stub=False) requires Phase C1")
    return SimpleNamespace(
        id=uuid.uuid4(),
        pk=uuid.uuid4(),
        study=study,
        study_id=study.id,
        condition_type=condition_type,
        event_name=event_name,
        is_active=is_active,
        **extra,
    )


def make_study_template(
    *,
    name: str = "Pricing feedback template",
    category: str = "pricing",
    interview_mode: str = "voice",
    is_system: bool = False,
    stub: bool = True,
    **extra: Any,
) -> SimpleNamespace:
    """Build a StudyTemplate."""
    if not stub:
        raise NotImplementedError("make_study_template(stub=False) requires Phase C1")
    return SimpleNamespace(
        id=uuid.uuid4(),
        pk=uuid.uuid4(),
        name=name,
        category=category,
        interview_mode=interview_mode,
        is_system=is_system,
        **extra,
    )


class _FakeRelated:
    """Minimal mock of a Django related manager (``study.goals.all()``, etc.)."""

    def __init__(self, items: list[Any]):
        self._items = items

    def add(self, item: Any) -> None:
        self._items.append(item)

    def all(self) -> list[Any]:
        return list(self._items)

    def count(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)
