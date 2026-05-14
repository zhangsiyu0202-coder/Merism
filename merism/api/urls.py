"""Merism API URL routing.

Single DRF router. Adding a viewset? Register it here and add a
``Section header``/comment to keep the grouping scannable.
"""

from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from merism.api import views
from merism.api.analysis_views import (
    CohortSegmentViewSet,
    CoverageSnapshotViewSet,
    StudyGoalViewSet,
    ThemeViewSet,
)
from merism.api.insights_views import (
    CustomReportViewSet,
    InsightFindingViewSet,
    InsightHighlightViewSet,
    ReportQuestionViewSet,
    ReportSegmentViewSet,
    StudyInsightsViewSet,
    shared_report_view,
)
from merism.api.cleaning_views import GlossaryViewSet
from merism.api.home import HomeStatsView
from merism.api.ask_views import ask_stream, knowledge_search
from merism.api.interview_message_view import post_message
from merism.api.link_tracking_views import LinkClickViewSet, LinkShareEventViewSet
from merism.api.users import UserMeView

router = DefaultRouter()

# ── Study domain ───────────────────────────────────────────
router.register(r"studies", views.StudyViewSet, basename="study")
router.register(r"inbox-items", views.InboxItemViewSet, basename="inboxitem")
router.register(r"study-links", views.StudyLinkViewSet, basename="studylink")
router.register(r"study-templates", views.StudyTemplateViewSet, basename="studytemplate")
router.register(r"study-triggers", views.StudyTriggerViewSet, basename="studytrigger")
router.register(r"screeners", views.ScreenerViewSet, basename="screener")
router.register(r"stimuli", views.StimulusViewSet, basename="stimulus")

# ── Concept testing ────────────────────────────────────────
router.register(r"concept-blocks", views.ConceptBlockViewSet, basename="conceptblock")
router.register(r"concepts", views.ConceptViewSet, basename="concept")

# ── Interview domain ───────────────────────────────────────
router.register(r"guides", views.InterviewGuideViewSet, basename="interviewguide")
router.register(r"participants", views.ParticipantViewSet, basename="participant")
router.register(r"participations", views.ParticipationViewSet, basename="participation")
router.register(r"sessions", views.InterviewSessionViewSet, basename="interviewsession")

# ── Knowledge domain ───────────────────────────────────────
router.register(r"knowledge/chunks", views.KnowledgeChunkViewSet, basename="knowledgechunk")
router.register(r"knowledge/documents", views.KnowledgeDocumentViewSet, basename="knowledgedocument")

# ── Recruitment domain ─────────────────────────────────────
router.register(r"channels", views.ChannelConfigViewSet, basename="channelconfig")
router.register(r"templates", views.MessageTemplateViewSet, basename="messagetemplate")
router.register(r"broadcasts", views.RecruitmentBroadcastViewSet, basename="recruitmentbroadcast")
router.register(r"deliveries", views.DeliveryRecordViewSet, basename="deliveryrecord")

# ── Report domain ──────────────────────────────────────────
router.register(r"reports", views.StudyReportViewSet, basename="studyreport")
router.register(r"insights", views.SessionInsightViewSet, basename="sessioninsight")
router.register(r"custom-report-queries", views.CustomReportQueryViewSet, basename="customreportquery")

# ── MEM AI / memory ────────────────────────────────────────
router.register(r"conversations", views.ConversationViewSet, basename="conversation")
router.register(r"memories", views.AgentMemoryViewSet, basename="agentmemory")

# ── LLM Gateway (DEPRECATED — removed, use ServiceSettings admin) ──

# ── Analysis (cross-session) ───────────────────────────────
router.register(r"study-goals", StudyGoalViewSet, basename="studygoal")
router.register(r"themes", ThemeViewSet, basename="theme")
router.register(r"coverage-snapshots", CoverageSnapshotViewSet, basename="coveragesnapshot")
router.register(r"cohort-segments", CohortSegmentViewSet, basename="cohortsegment")

# ── Cleaning (transcript pipeline) ─────────────────────────
router.register(r"glossaries", GlossaryViewSet, basename="glossary")

# ── Insights & Custom Reports ──────────────────────────────
router.register(r"study-insights", StudyInsightsViewSet, basename="studyinsights")
router.register(r"insight-highlights", InsightHighlightViewSet, basename="insighthighlight")
router.register(r"insight-findings", InsightFindingViewSet, basename="insightfinding")
router.register(r"custom-reports", CustomReportViewSet, basename="customreport2")
router.register(r"report-segments", ReportSegmentViewSet, basename="reportsegment")
router.register(r"report-questions", ReportQuestionViewSet, basename="reportquestion")

# ── Link tracking ──────────────────────────────────────────
router.register(r"link-clicks", LinkClickViewSet, basename="linkclick")
router.register(r"link-share-events", LinkShareEventViewSet, basename="linkshareevent")

urlpatterns = [
    path("users/me/", UserMeView.as_view(), name="user-me"),
    path("home/stats/", HomeStatsView.as_view(), name="home-stats"),
    path("ask/stream/", ask_stream, name="ask-stream"),
    path("sessions/<uuid:session_id>/message/", post_message, name="session-message"),
    path("knowledge/search/", knowledge_search, name="knowledge-search"),
    path("shared/report/<str:token>/", shared_report_view, name="shared-report"),
    path("", include(router.urls)),
]
