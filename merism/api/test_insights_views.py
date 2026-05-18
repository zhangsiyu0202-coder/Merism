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
