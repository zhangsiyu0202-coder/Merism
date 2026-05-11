"""Merism models — single-app, flat namespace.

Every model is defined under ``merism.models.<domain>`` and re-exported
here for Django's app-registry discovery and for ``from merism.models
import Team, Study, ...`` ergonomics.
"""

from __future__ import annotations

from merism.models.concept import Concept, ConceptBlock, ConceptRotationCursor
from merism.models.interview import (
    InterviewGuide,
    InterviewRecording,
    InterviewSession,
    Participant,
    Participation,
)
from merism.models.knowledge import (
    EMBEDDING_DIM,
    KnowledgeChunk,
    KnowledgeDocument,
    StudyKnowledgeBase,
    TeamResearchKnowledgeBase,
)
from merism.models.memory import AgentMemory, Conversation, CoreMemory
from merism.models.recruitment import (
    ChannelConfig,
    ChannelHealthCheck,
    DeliveryRecord,
    MessageTemplate,
    RecruitmentBroadcast,
)
from merism.models.report import (
    AggregateSynthesis,
    CustomReportQuery,
    SessionInsight,
    StudyReport,
)
from merism.models.inbox import InboxItem
from merism.models.invitation import Invitation
from merism.models.session_event import SessionEvent
from merism.models.session_quote import SessionQuote
from merism.models.stimulus import Screener, Stimulus
from merism.models.study import Study, StudyLink, StudyTemplate, StudyTrigger
from merism.models.team import (
    Organization,
    OrganizationMembership,
    Team,
    TimestampedModel,
    UUIDModel,
    team_id_field,
)

__all__ = [
    # team / org
    "Organization",
    "OrganizationMembership",
    "Team",
    "TimestampedModel",
    "UUIDModel",
    "team_id_field",
    # study
    "Study",
    "StudyLink",
    "StudyTemplate",
    "StudyTrigger",
    # stimulus / screener
    "Screener",
    "Stimulus",
    # concept testing
    "Concept",
    "ConceptBlock",
    "ConceptRotationCursor",
    # interview
    "InterviewGuide",
    "InterviewRecording",
    "InterviewSession",
    "Participant",
    "Participation",
    # knowledge
    "EMBEDDING_DIM",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "StudyKnowledgeBase",
    "TeamResearchKnowledgeBase",
    # recruitment
    "ChannelConfig",
    "ChannelHealthCheck",
    "DeliveryRecord",
    "MessageTemplate",
    "RecruitmentBroadcast",
    # reports
    "AggregateSynthesis",
    "CustomReportQuery",
    "SessionInsight",
    "StudyReport",
    # session quotes
    "SessionEvent",
    "SessionQuote",
    # memory
    "AgentMemory",
    "Conversation",
    "CoreMemory",
]
