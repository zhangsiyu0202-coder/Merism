"""Tests for Insights & Custom Reports models, API, and tasks."""

from __future__ import annotations

from django.test import TestCase
from rest_framework.test import APIClient

from merism.models import (
    CustomReport,
    InsightFinding,
    InsightHighlight,
    Organization,
    OrganizationMembership,
    ReportQuestion,
    ReportSegment,
    Study,
    StudyInsights,
)
from merism.testing import MerismAPITestCase


class TestModelDbTablePrefix(TestCase):
    def test_insights_models_have_merism_prefix(self):
        assert StudyInsights._meta.db_table == "merism_study_insights"
        assert InsightHighlight._meta.db_table == "merism_insight_highlight"
        assert InsightFinding._meta.db_table == "merism_insight_finding"

    def test_report_models_have_merism_prefix(self):
        assert CustomReport._meta.db_table == "merism_custom_report"
        assert ReportSegment._meta.db_table == "merism_report_segment"
        assert ReportQuestion._meta.db_table == "merism_report_question"


class TestInsightsAPI(MerismAPITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.organization = Organization.objects.create(name="Acme", slug="acme-ins")
        cls.team = cls.organization.teams.create(name="Research")
        OrganizationMembership.objects.create(
            organization=cls.organization,
            user=cls.user,
            role=OrganizationMembership.Role.OWNER,
        )
        cls.study = Study.objects.create(
            team=cls.team,
            created_by=cls.user,
            name="Test Study",
            research_goal="Test goal",
            status=Study.Status.DRAFT,
        )
        cls.insights = StudyInsights.objects.create(
            team=cls.team,
            study=cls.study,
            status=StudyInsights.Status.READY,
            completed_interviews=5,
            executive_summary="Test summary",
        )

    def test_list_insights(self):
        response = self.client.get(f"/api/study-insights/?study={self.study.id}")
        assert response.status_code == 200
        data = response.json()
        results = data.get("results", data)
        assert len(results) == 1
        assert results[0]["executive_summary"] == "Test summary"

    def test_rerun_insights(self):
        from unittest.mock import patch

        with patch("merism.api.insights_tasks.generate_insights_task.delay"):
            response = self.client.post(f"/api/study-insights/{self.insights.id}/rerun/")
        assert response.status_code == 202
        self.insights.refresh_from_db()
        assert self.insights.status == "generating"

    def test_status_derived_from_data_when_field_is_stale(self):
        """The serializer should report ``ready`` when the data is fully
        populated, even if the status column is stuck at ``generating``.

        This guards against the stuck-task race: a worker dies after
        finishing data writes but before its successful ``status=READY``
        save commits, OR a rerun() races with the task's final save.
        Either way, the user shouldn't see "generating" forever when
        the report is actually done.
        """
        from django.utils import timezone

        # Use a separate study — StudyInsights has a unique constraint
        # on study_id, and setUpTestData already wired one to cls.study.
        study = Study.objects.create(
            team=self.team,
            created_by=self.user,
            name="Stale Status Study",
            research_goal="goal",
            status=Study.Status.DRAFT,
        )
        si = StudyInsights.objects.create(
            team=self.team,
            study=study,
            status=StudyInsights.Status.GENERATING,
            executive_summary="A real summary",
            completed_interviews=9,
            generated_at=timezone.now(),
        )
        InsightHighlight.objects.create(
            team=self.team,
            insights=si,
            headline="h",
            summary="s",
            display_order=0,
        )
        InsightFinding.objects.create(
            team=self.team,
            insights=si,
            title="t",
            summary="s",
            display_order=0,
        )

        response = self.client.get(f"/api/study-insights/?study={study.id}")
        assert response.status_code == 200
        results = response.json().get("results", response.json())
        assert len(results) == 1
        # The stuck row appears with status=ready (derived) even though
        # the DB column still says generating.
        assert results[0]["status"] == "ready"
        # Confirm the DB column is unchanged — the fix is read-side only.
        si.refresh_from_db()
        assert si.status == "generating"

    def test_status_passes_through_when_data_incomplete(self):
        """If data isn't complete BUT generation is still possible
        (the study has at least one completed participation), pass
        through the column value — protect the legitimate fresh
        in-flight state where the worker is still chewing.
        """
        from merism.models import Participation

        study = Study.objects.create(
            team=self.team,
            created_by=self.user,
            name="No Data Study",
            research_goal="goal",
            status=Study.Status.DRAFT,
        )
        # Add a completed participation so ``actual_completed_count`` > 0
        # — without this, the new rule "no sessions ⇒ status=failed"
        # short-circuits the in-flight state.
        Participation.objects.create(
            team=self.team,
            study=study,
            status=Participation.Status.COMPLETED,
        )
        StudyInsights.objects.create(
            team=self.team,
            study=study,
            status=StudyInsights.Status.GENERATING,
            executive_summary="",
        )
        response = self.client.get(f"/api/study-insights/?study={study.id}")
        results = response.json().get("results", response.json())
        assert len(results) == 1
        assert results[0]["status"] == "generating"

    def test_status_failed_when_stuck_with_no_completed_interviews(self):
        """A StudyInsights record stuck at ``generating`` for a study
        that has no completed participations is reported as
        ``failed`` — the underlying task can never succeed (it would
        bail with "No completed interviews to analyze") so polling
        the row forever is pointless. The frontend sees ``failed``,
        surfaces the empty state + re-run button, and the user can
        actually do something.
        """
        study = Study.objects.create(
            team=self.team,
            created_by=self.user,
            name="No Sessions Study",
            research_goal="goal",
            status=Study.Status.DRAFT,
        )
        # No Participation at all — actual_completed_count == 0.
        StudyInsights.objects.create(
            team=self.team,
            study=study,
            status=StudyInsights.Status.GENERATING,
            executive_summary="",
        )
        response = self.client.get(f"/api/study-insights/?study={study.id}")
        results = response.json().get("results", response.json())
        assert len(results) == 1
        assert results[0]["status"] == "failed"
        assert "无已完成的访谈" in results[0]["error_message"]


class TestCustomReportAPI(MerismAPITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.organization = Organization.objects.create(name="Acme", slug="acme-rpt")
        cls.team = cls.organization.teams.create(name="Research")
        OrganizationMembership.objects.create(
            organization=cls.organization,
            user=cls.user,
            role=OrganizationMembership.Role.OWNER,
        )
        cls.study = Study.objects.create(
            team=cls.team,
            created_by=cls.user,
            name="Test Study",
            research_goal="Test goal",
            status=Study.Status.DRAFT,
        )

    def setUp(self):
        super().setUp()
        self.report = CustomReport.objects.create(
            team=self.team,
            study=self.study,
            title="Test Report",
            created_by=self.user,
        )

    def test_list_reports(self):
        response = self.client.get(f"/api/custom-reports/?study={self.study.id}")
        assert response.status_code == 200
        data = response.json()
        results = data.get("results", data)
        assert len(results) == 1

    def test_create_report(self):
        response = self.client.post(
            "/api/custom-reports/",
            {
                "study": str(self.study.id),
                "title": "New Report",
            },
        )
        assert response.status_code == 201

    def test_toggle_public(self):
        assert not self.report.is_public
        response = self.client.post(f"/api/custom-reports/{self.report.id}/toggle_public/")
        assert response.status_code == 200
        self.report.refresh_from_db()
        assert self.report.is_public

    def test_export_csv(self):
        ReportQuestion.objects.create(
            team=self.team,
            report=self.report,
            title="Test Q",
            question_number=1,
            status=ReportQuestion.Status.READY,
            ai_summary="Summary",
        )
        response = self.client.get(f"/api/custom-reports/{self.report.id}/export_csv/")
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"

    def test_shared_report_public(self):
        self.report.is_public = True
        self.report.save()
        anon = APIClient()
        response = anon.get(f"/api/shared/report/{self.report.share_token}/")
        assert response.status_code == 200
        assert response.json()["title"] == "Test Report"

    def test_shared_report_not_public_returns_404(self):
        anon = APIClient()
        response = anon.get(f"/api/shared/report/{self.report.share_token}/")
        assert response.status_code == 404

    def test_share_token_unique(self):
        r2 = CustomReport.objects.create(team=self.team, study=self.study, title="R2")
        assert self.report.share_token != r2.share_token


class TestReportQuestionAPI(MerismAPITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.organization = Organization.objects.create(name="Acme", slug="acme-rq")
        cls.team = cls.organization.teams.create(name="Research")
        OrganizationMembership.objects.create(
            organization=cls.organization,
            user=cls.user,
            role=OrganizationMembership.Role.OWNER,
        )
        cls.study = Study.objects.create(
            team=cls.team,
            created_by=cls.user,
            name="Test Study",
            research_goal="Test goal",
            status=Study.Status.DRAFT,
        )

    def setUp(self):
        super().setUp()
        self.report = CustomReport.objects.create(team=self.team, study=self.study, title="R")

    def test_create_question(self):
        response = self.client.post(
            "/api/report-questions/",
            {
                "report": str(self.report.id),
                "title": "What do users think?",
                "question_type": "open_ended",
                "question_number": 1,
            },
        )
        assert response.status_code == 201

    def test_list_questions(self):
        ReportQuestion.objects.create(team=self.team, report=self.report, title="Q1", question_number=1)
        response = self.client.get(f"/api/report-questions/?report={self.report.id}")
        assert response.status_code == 200
        data = response.json()
        results = data.get("results", data)
        assert len(results) == 1
