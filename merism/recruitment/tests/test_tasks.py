from __future__ import annotations

from unittest.mock import patch

from merism.models import (
    ChannelConfig,
    DeliveryRecord,
    MessageTemplate,
    Organization,
    RecruitmentBroadcast,
    Study,
    StudyLink,
    Team,
)
from merism.recruitment.tasks import dispatch_recruitment_delivery
from merism.testing import InMemoryIMAdapter, MerismTestCase


class TestDispatchRecruitmentDelivery(MerismTestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.organization = Organization.objects.create(name="Acme", slug="acme-tasks")
        cls.team = Team.objects.create(organization=cls.organization, name="Research")
        cls.study = Study.objects.create(
            team=cls.team,
            research_goal="Understand recruiting response rates.",
            name="Recruiting study",
            target_audience="QQ and WeCom group members who fit our target profile.",
            target_completed_count=5,
            status=Study.Status.LIVE,
        )
        cls.study_link = StudyLink.objects.create(study=cls.study, team=cls.team)

    def test_dispatch_uses_group_send_for_group_recipients(self) -> None:
        channel = ChannelConfig.objects.create(
            team=self.team,
            channel_type=ChannelConfig.ChannelType.QQ_GROUP,
            name="QQ outreach",
            status=ChannelConfig.Status.ACTIVE,
        )
        template = MessageTemplate.objects.create(
            team=self.team,
            name="Invite template",
            channel_type=channel.channel_type,
            content="Join {{study_name}} here: {{study_link}}",
        )
        broadcast = RecruitmentBroadcast.objects.create(
            team=self.team,
            study=self.study,
            study_link=self.study_link,
            channel=channel,
            template=template,
            status=RecruitmentBroadcast.Status.APPROVED,
            approved_snapshot={
                "template_content": "Join {{study_name}} here: {{study_link}}",
                "msg_format": "markdown",
            },
            counters={"total": 1, "sent": 0, "failed": 0, "pending": 1},
        )
        delivery = DeliveryRecord.objects.create(
            team=self.team,
            broadcast=broadcast,
            recipient_id="qq-group-openid",
            recipient_kind="group",
            status=DeliveryRecord.Status.PENDING,
        )

        adapter = InMemoryIMAdapter(channel_type="qq_group")

        with patch("merism.recruitment.tasks.decrypt_credentials", return_value={}), patch(
            "merism.recruitment.tasks.get_adapter",
            return_value=adapter,
        ), patch(
            "merism.recruitment.tasks.check_and_increment_rate",
            return_value=(True, 1),
        ):
            counters = dispatch_recruitment_delivery(str(broadcast.id))

        delivery.refresh_from_db()
        broadcast.refresh_from_db()
        assert counters["sent"] == 1
        assert delivery.status == DeliveryRecord.Status.SENT
        assert broadcast.status == RecruitmentBroadcast.Status.COMPLETED
        assert adapter.last_message.group_target is True
        assert adapter.last_message.recipient_id == "qq-group-openid"
        assert "https://merism.test/i/" in adapter.last_message.content
        assert "?t=" not in adapter.last_message.content
