from __future__ import annotations

from unittest.mock import patch

from merism.memai.agents.recruitment_message import RecruitmentMessage
from merism.models import (
    ChannelConfig,
    ChannelTarget,
    DeliveryRecord,
    Organization,
    OrganizationMembership,
    RecruitmentBroadcast,
    Study,
)
from merism.testing import MerismAPITestCase


class TestStudyLaunchRecruitmentAction(MerismAPITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.organization = Organization.objects.create(name="Acme", slug="acme")
        cls.team = cls.organization.teams.create(name="Research")
        OrganizationMembership.objects.create(
            organization=cls.organization,
            user=cls.user,
            role=OrganizationMembership.Role.OWNER,
        )
        cls.study = Study.objects.create(
            team=cls.team,
            created_by=cls.user,
            name="Signup interviews",
            research_goal="Understand who is willing to join a signup study.",
            target_audience="Chinese knowledge workers who use productivity tools weekly.",
            target_completed_count=8,
            estimated_minutes=25,
            status=Study.Status.DRAFT,
        )

    def test_launch_recruitment_creates_broadcasts_and_deliveries(self) -> None:
        qq_channel = ChannelConfig.objects.create(
            team=self.team,
            channel_type=ChannelConfig.ChannelType.QQ_GROUP,
            name="QQ outreach",
            status=ChannelConfig.Status.ACTIVE,
        )
        wecom_channel = ChannelConfig.objects.create(
            team=self.team,
            channel_type=ChannelConfig.ChannelType.WECOM_BOT,
            name="WeCom outreach",
            status=ChannelConfig.Status.ACTIVE,
        )
        ChannelTarget.objects.create(
            team=self.team,
            channel=qq_channel,
            name="QQ Group A",
            recipient_id="qq-group-openid",
            is_default=True,
        )
        ChannelTarget.objects.create(
            team=self.team,
            channel=wecom_channel,
            name="WeCom Group A",
            recipient_id="wecom-group-a",
            is_default=True,
        )

        messages = [
            RecruitmentMessage(
                title="QQ recruit",
                body_markdown="QQ群招募: {{study_link}}",
                body_text="QQ群招募: {{study_link}}",
            ),
            RecruitmentMessage(
                title="WeCom recruit",
                body_markdown="企微群招募: {{study_link}}",
                body_text="企微群招募: {{study_link}}",
            ),
        ]

        with patch(
            "merism.recruitment.orchestrator.generate_recruitment_message",
            side_effect=messages,
        ), patch("merism.recruitment.tasks.dispatch_recruitment_delivery.delay") as delay_mock:
            response = self.client.post(f"/api/studies/{self.study.id}/launch-recruitment/")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload["queued_broadcast_ids"]) == 2
        assert payload["created_count"] == 2
        assert payload["errors"] == []
        assert RecruitmentBroadcast.objects.filter(study=self.study).count() == 2
        assert DeliveryRecord.objects.filter(broadcast__study=self.study).count() == 2
        self.study.refresh_from_db()
        assert self.study.status == Study.Status.LIVE
        assert delay_mock.call_count == 2

    def test_launch_recruitment_returns_400_without_active_channels(self) -> None:
        response = self.client.post(f"/api/studies/{self.study.id}/launch-recruitment/")

        assert response.status_code == 400
        assert response.json()["detail"] == "No active recruitment channels are configured for this team."
