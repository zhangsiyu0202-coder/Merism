from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from merism.memai.agents.recruitment_message import (
    RecruitmentMessage,
    generate_recruitment_message,
)
from merism.models import (
    ChannelConfig,
    DeliveryRecord,
    MessageTemplate,
    Participant,
    Participation,
    RecruitmentBroadcast,
    Study,
    StudyLink,
)
from merism.recruitment import encrypt_credentials


@dataclass(frozen=True)
class EmailSenderConfig:
    host: str
    port: int
    use_tls: bool
    username: str
    password: str
    from_address: str
    reply_to: str = ""


@dataclass(frozen=True)
class ParticipantEmailRecruitmentResult:
    broadcast_id: str
    recipient_count: int
    skipped_existing_count: int


def launch_participant_email_recruitment(
    *,
    study: Study,
    sender_config: EmailSenderConfig,
    limit: int | None = None,
) -> ParticipantEmailRecruitmentResult:
    study_link = _get_or_create_study_link(study)
    channel = _get_or_create_email_channel(study=study, sender_config=sender_config)
    recipients = _participant_recipient_emails(study=study, limit=limit)
    if not recipients:
        raise ValueError("No participant email rows found for this study.")

    message = generate_recruitment_message(
        study=study,
        study_link=_absolute_study_link(study_link),
        channel_type=ChannelConfig.ChannelType.EMAIL,
    )
    broadcast = _create_email_broadcast(
        study=study,
        study_link=study_link,
        channel=channel,
        message=message,
        recipients=recipients,
    )

    from merism.recruitment.tasks import dispatch_recruitment_delivery

    dispatch_recruitment_delivery.delay(str(broadcast.id))
    return ParticipantEmailRecruitmentResult(
        broadcast_id=str(broadcast.id),
        recipient_count=len(recipients),
        skipped_existing_count=0,
    )


def _get_or_create_study_link(study: Study) -> StudyLink:
    existing = StudyLink.objects.filter(study=study, is_active=True).order_by("-created_at").first()
    if existing is not None:
        return existing
    return StudyLink.objects.create(study=study, team=study.team)


def _absolute_study_link(study_link: StudyLink) -> str:
    if study_link.short_link_domain:
        return f"https://{study_link.short_link_domain}{study_link.url_path}"
    return f"https://merism.test{study_link.url_path}"


def _get_or_create_email_channel(
    *,
    study: Study,
    sender_config: EmailSenderConfig,
) -> ChannelConfig:
    credentials = {
        "transport": "smtp",
        "host": sender_config.host,
        "port": sender_config.port,
        "use_tls": sender_config.use_tls,
        "username": sender_config.username,
        "password": sender_config.password,
        "from_address": sender_config.from_address,
        "reply_to": sender_config.reply_to,
    }
    channel, _created = ChannelConfig.objects.get_or_create(
        team=study.team,
        channel_type=ChannelConfig.ChannelType.EMAIL,
        name="Participant email sender",
        defaults={"status": ChannelConfig.Status.ACTIVE},
    )
    channel.credentials_encrypted = encrypt_credentials(credentials)
    channel.status = ChannelConfig.Status.ACTIVE
    channel.last_error = ""
    channel.save(
        update_fields=[
            "credentials_encrypted",
            "status",
            "last_error",
            "updated_at",
        ]
    )
    return channel


def _participant_recipient_emails(*, study: Study, limit: int | None) -> list[str]:
    candidates = Participant.objects.filter(team=study.team).order_by("created_at")
    if limit is not None:
        candidates = candidates[:limit]
    return [participant.email for participant in candidates]


def _system_template() -> MessageTemplate:
    template, _ = MessageTemplate.objects.get_or_create(
        team=None,
        is_system=True,
        channel_type=ChannelConfig.ChannelType.EMAIL,
        name="AI-generated participant email",
        defaults={"content": "{{study_name}}\n{{study_link}}"},
    )
    return template


@transaction.atomic
def _create_email_broadcast(
    *,
    study: Study,
    study_link: StudyLink,
    channel: ChannelConfig,
    message: RecruitmentMessage,
    recipients: list[str],
) -> RecruitmentBroadcast:
    template = _system_template()
    broadcast = RecruitmentBroadcast.objects.create(
        team=study.team,
        study=study,
        study_link=study_link,
        channel=channel,
        template=template,
        status=RecruitmentBroadcast.Status.APPROVED,
        approved_snapshot={
            "title": message.title,
            "template_content": message.body_text,
            "body_markdown": message.body_markdown,
            "body_text": message.body_text,
            "msg_format": "text",
            "generated_by": "merism.memai.agents.recruitment_message",
        },
        counters={
            "total": len(recipients),
            "sent": 0,
            "failed": 0,
            "pending": len(recipients),
        },
    )
    DeliveryRecord.objects.bulk_create(
        [
            DeliveryRecord(
                team=study.team,
                broadcast=broadcast,
                recipient_id=recipient,
                recipient_kind=Participation.Source.EMAIL,
                status=DeliveryRecord.Status.PENDING,
            )
            for recipient in recipients
        ]
    )
    return broadcast
