"""Report / synthesis factories.

AggregateSynthesis (study-wide analysis rollup), SessionInsight (per-session
quick insight), StudyReport (final deliverable with block schema).
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any


def make_session_insight(
    session: SimpleNamespace,
    *,
    headline: str = "Participant expressed frustration with pricing",
    themes: list[str] | None = None,
    quotes: list[dict[str, Any]] | None = None,
    stub: bool = True,
) -> SimpleNamespace:
    """Build a SessionInsight for one interview session."""
    if not stub:
        raise NotImplementedError("make_session_insight(stub=False) requires Phase C1")
    return SimpleNamespace(
        id=uuid.uuid4(),
        pk=uuid.uuid4(),
        session=session,
        session_id=session.id,
        headline=headline,
        themes=themes or [],
        quotes=quotes or [],
    )


def make_aggregate_synthesis(
    study: SimpleNamespace,
    *,
    headline: str = "Pricing is the top pain point across 5 sessions",
    themes: list[dict[str, Any]] | None = None,
    covered_goals: list[str] | None = None,
    stub: bool = True,
) -> SimpleNamespace:
    """Build an AggregateSynthesis for a study."""
    if not stub:
        raise NotImplementedError("make_aggregate_synthesis(stub=False) requires Phase C1")
    return SimpleNamespace(
        id=uuid.uuid4(),
        pk=uuid.uuid4(),
        study=study,
        study_id=study.id,
        team_id=study.team_id,
        headline=headline,
        themes=themes or [],
        covered_goals=covered_goals or [],
    )


def make_study_report(
    study: SimpleNamespace,
    *,
    status: str = "draft",
    blocks: list[dict[str, Any]] | None = None,
    generated_by: str = "test",
    stub: bool = True,
) -> SimpleNamespace:
    """Build a StudyReport. Blocks follow the text/metric/quote/chart schema.

    ``blocks`` defaults to a minimal valid document with one text block.
    """
    if not stub:
        raise NotImplementedError("make_study_report(stub=False) requires Phase C1")
    return SimpleNamespace(
        id=uuid.uuid4(),
        pk=uuid.uuid4(),
        study=study,
        study_id=study.id,
        team_id=study.team_id,
        status=status,
        blocks=blocks or [{"type": "text", "body": "Summary goes here."}],
        generated_by=generated_by,
    )
