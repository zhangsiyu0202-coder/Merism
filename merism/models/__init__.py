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
from merism.models.memory import AgentMemory, AskArtifact, Conversation, CoreMemory
from merism.models.recruitment import (
    ChannelConfig,
    ChannelHealthCheck,
    ChannelTarget,
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
from merism.models.insights import InsightFinding, InsightHighlight, StudyInsights
from merism.models.custom_report import CustomReport, ReportQuestion, ReportSegment
from merism.models.inbox import InboxItem
from merism.models.invitation import Invitation
from merism.models.link_tracking import LinkClick, LinkShareEvent
from merism.models.analysis import CohortSegment, CoverageSnapshot, StudyGoal, Theme
from merism.models.glossary import Glossary
from merism.models.service_settings import ServiceSettings
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
    "ChannelTarget",
    "DeliveryRecord",
    "MessageTemplate",
    "RecruitmentBroadcast",
    # reports
    "AggregateSynthesis",
    "CustomReportQuery",
    "SessionInsight",
    "StudyReport",
    # insights (auto-generated)
    "InsightFinding",
    "InsightHighlight",
    "StudyInsights",
    # custom reports (user-created)
    "CustomReport",
    "ReportQuestion",
    "ReportSegment",
    # session quotes
    "SessionEvent",
    "SessionQuote",
    # link tracking
    "LinkClick",
    "LinkShareEvent",
    # memory
    "AgentMemory",
    "AskArtifact",
    "Conversation",
    "CoreMemory",
    # service settings
    "ServiceSettings",
    # analysis
    "CohortSegment",
    "CoverageSnapshot",
    "StudyGoal",
    "Theme",
    # cleaning
    "Glossary",
]

# codebook governance
from merism.codebook.models import CodebookVersion, CodeChange, CodeMapping

__all__ += [
    "CodebookVersion",
    "CodeChange",
    "CodeMapping",
]
