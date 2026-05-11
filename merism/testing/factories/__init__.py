"""Merism domain factories.

Every factory accepts ``stub=True`` (the default while on the lightweight
test entry) to return a ``SimpleNamespace`` with the minimum shape the
corresponding Django model exposes. When ``stub=False`` the factory writes
a real row (requires ``merism.Team`` — Phase C1).

Submodules are organized by Merism domain, not by Django app:

- :mod:`merism.testing.factories.study`        — Study, StudyGoal, StudyTrigger, StudyLink, StudyTemplate
- :mod:`merism.testing.factories.interview`    — InterviewSession, InterviewGuide, Participation, Participant, Turn
- :mod:`merism.testing.factories.conductor`    — ExecutionState, policy contexts
- :mod:`merism.testing.factories.knowledge`    — KnowledgeChunk, KnowledgeDocument, StudyKnowledgeBase, TeamResearchKnowledgeBase
- :mod:`merism.testing.factories.recruitment`  — ChannelConfig, RecruitmentBroadcast, MessageTemplate, DeliveryRecord
- :mod:`merism.testing.factories.report`       — AggregateSynthesis, SessionInsight, StudyReport
"""

from __future__ import annotations

from merism.testing.factories.interview import make_interview, make_turn
from merism.testing.factories.study import make_study, make_study_with_goals

__all__ = [
    "make_study",
    "make_study_with_goals",
    "make_interview",
    "make_turn",
]
