from __future__ import annotations

from unittest.mock import patch

from merism.memai.agents.recruitment_message import RecruitmentMessage
from merism.models import (
    ChannelConfig,
    DeliveryRecord,
    MessageTemplate,
    Organization,
    OrganizationMembership,
    Participant,
    Participation,
    RecruitmentBroadcast,
    Study,
    Team,
)
from merism.recruitment.participant_email_recruitment import (
    EmailSenderConfig,
    launch_participant_email_recruitment,
)
from merism.recruitment.tasks import dispatch_recruitment_delivery
from merism.recruitment.adapters.base import SendResult
from merism.testing import MerismTestCase


class TestParticipantEmailRecruitment(MerismTestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.organization = Organization.objects.create(name="Acme", slug="acme-email-flow")
        cls.team = Team.objects.create(organization=cls.organization, name="Research")
        OrganizationMembership.objects.create(
            organization=cls.organization,
            user=cls.user,
            role=OrganizationMembership.Role.OWNER,
        )
        cls.study = Study.objects.create(
            team=cls.team,
            created_by=cls.user,
            name="Email outreach study",
            research_goal="Understand willingness to join a user interview.",
            target_audience="Existing product users with valid email addresses.",
            target_completed_count=5,
            status=Study.Status.DRAFT,
        )

    def test_launch_creates_email_broadcast_from_participant_emails(self) -> None:
        Participant.objects.create(team=self.team, email="first@example.com", name="First")
        Participant.objects.create(team=self.team, email="FIRST@example.com", name="Duplicate")
        Participant.objects.create(team=self.team, email="", name="Blank")
        already_in_study = Participant.objects.create(
            team=self.team,
            email="done@example.com",
            name="Done",
        )
        Participation.objects.create(team=self.team, study=self.study, participant=already_in_study)

        sender_config = EmailSenderConfig(
            host="smtp.example.com",
            port=587,
            use_tls=True,
            username="sender@example.com",
            password="secret",
            from_address="Sender <sender@example.com>",
            reply_to="reply@example.com",
        )
        generated = RecruitmentMessage(
            title="Join our research study",
            body_markdown="Join **{{study_name}}** here: {{study_link}}",
            body_text="Join {{study_name}} here: {{study_link}}",
        )

        with patch(
            "merism.recruitment.participant_email_recruitment.generate_recruitment_message",
            return_value=generated,
        ), patch("merism.recruitment.tasks.dispatch_recruitment_delivery.delay") as delay_mock:
            result = launch_participant_email_recruitment(
                study=self.study,
                sender_config=sender_config,
            )

        channel = ChannelConfig.objects.get(team=self.team, channel_type=ChannelConfig.ChannelType.EMAIL)
        broadcast = RecruitmentBroadcast.objects.get(id=result.broadcast_id)
        deliveries = list(
            DeliveryRecord.objects.filter(broadcast=broadcast).order_by("recipient_id")
        )

        assert channel.status == ChannelConfig.Status.ACTIVE
        assert result.recipient_count == 4
        assert broadcast.approved_snapshot["title"] == "Join our research study"
        assert [delivery.recipient_id for delivery in deliveries] == [
            "",
            "FIRST@example.com",
            "done@example.com",
            "first@example.com",
        ]
        delay_mock.assert_called_once_with(str(broadcast.id))

    def test_dispatch_passes_subject_into_email_message(self) -> None:
        channel = ChannelConfig.objects.create(
            team=self.team,
            channel_type=ChannelConfig.ChannelType.EMAIL,
            name="Email sender",
            status=ChannelConfig.Status.ACTIVE,
        )
        template = MessageTemplate.objects.create(
            team=self.team,
            name="Invite template",
            channel_type=ChannelConfig.ChannelType.EMAIL,
            content="Hello {{study_name}} {{study_link}}",
        )
        broadcast = RecruitmentBroadcast.objects.create(
            team=self.team,
            study=self.study,
            channel=channel,
            template=template,
            status=RecruitmentBroadcast.Status.APPROVED,
            approved_snapshot={
                "title": "Subject line",
                "template_content": "Hello {{study_name}} {{study_link}}",
                "body_text": "Hello {{study_name}} {{study_link}}",
                "msg_format": "text",
            },
            counters={"total": 1, "sent": 0, "failed": 0, "pending": 1},
        )
        DeliveryRecord.objects.create(
            team=self.team,
            broadcast=broadcast,
            recipient_id="target@example.com",
            recipient_kind="user",
            status=DeliveryRecord.Status.PENDING,
        )

        class RecordingAdapter:
            def __init__(self) -> None:
                self.messages = []

            def send_message(self, recipient_id: str, message) -> SendResult:
                self.messages.append((recipient_id, message))
                return SendResult(success=True, message_id="msg-1")

            def send_to_group(self, group_id: str, message) -> SendResult:
                return self.send_message(group_id, message)

        adapter = RecordingAdapter()

        with patch("merism.recruitment.tasks.decrypt_credentials", return_value={}), patch(
            "merism.recruitment.tasks.get_adapter",
            return_value=adapter,
        ), patch(
            "merism.recruitment.tasks.check_and_increment_rate",
            return_value=(True, 1),
        ):
            dispatch_recruitment_delivery(str(broadcast.id))

        assert adapter.messages[0][0] == "target@example.com"
        assert adapter.messages[0][1].extra == {
            "subject": "Subject line",
            "text_alt": "Hello {{study_name}} {{study_link}}",
        }
