"""One-click recruitment orchestration.

Bridges the Recruit tab's single button into the existing
`RecruitmentBroadcast -> DeliveryRecord -> Celery -> adapter` pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.db import transaction

from merism.memai.agents.recruitment_message import generate_recruitment_message
from merism.models import (
    ChannelConfig,
    ChannelTarget,
    DeliveryRecord,
    MessageTemplate,
    RecruitmentBroadcast,
    Study,
    StudyLink,
)


@dataclass
class LaunchRecruitmentResult:
    queued_broadcast_ids: list[str] = field(default_factory=list)
    created_count: int = 0
    skipped_channels: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "queued_broadcast_ids": self.queued_broadcast_ids,
            "created_count": self.created_count,
            "skipped_channels": self.skipped_channels,
            "errors": self.errors,
        }


class RecruitmentLaunchError(ValueError):
    """Raised when the study is not eligible for one-click recruitment."""


def launch_study_recruitment(*, study: Study) -> LaunchRecruitmentResult:
    _validate_study(study)

    channels = list(
        ChannelConfig.objects.filter(team=study.team, status=ChannelConfig.Status.ACTIVE).order_by(
            "created_at"
        )
    )
    if not channels:
        raise RecruitmentLaunchError("No active recruitment channels are configured for this team.")

    study_link = _get_or_create_study_link(study)
    result = LaunchRecruitmentResult()

    for channel in channels:
        targets = list(
            ChannelTarget.objects.filter(
                team=study.team,
                channel=channel,
                is_active=True,
                is_default=True,
            ).order_by("created_at")
        )
        if not targets:
            result.skipped_channels.append(
                {
                    "channel_id": str(channel.id),
                    "channel_name": channel.name,
                    "reason": "no_default_targets",
                }
            )
            continue

        try:
            message = generate_recruitment_message(
                study=study,
                study_link=_absolute_study_link(study_link),
                channel_type=channel.channel_type,
            )
        except Exception as exc:
            result.errors.append(f"{channel.name}: {exc}")
            continue

        broadcast = _create_broadcast(
            study=study,
            study_link=study_link,
            channel=channel,
            targets=targets,
            message=message,
        )
        _enqueue_broadcast(broadcast)
        result.queued_broadcast_ids.append(str(broadcast.id))
        result.created_count += len(targets)

    if result.created_count > 0 and study.status == Study.Status.DRAFT:
        study.status = Study.Status.LIVE
        study.save(update_fields=["status", "updated_at"])

    return result


def _validate_study(study: Study) -> None:
    if study.status == Study.Status.CLOSED:
        raise RecruitmentLaunchError(
            f"Study cannot recruit participants while in status '{study.status}'."
        )
    if not study.research_goal.strip():
        raise RecruitmentLaunchError("Study research_goal is required before recruiting.")
    if not study.target_audience.strip():
        raise RecruitmentLaunchError("Describe the target audience before launching recruitment.")
    if study.target_completed_count < 1:
        raise RecruitmentLaunchError("target_completed_count must be at least 1.")


def _get_or_create_study_link(study: Study) -> StudyLink:
    existing = StudyLink.objects.filter(study=study, is_active=True).order_by("-created_at").first()
    if existing is not None:
        return existing
    return StudyLink.objects.create(study=study, team=study.team)


def _absolute_study_link(study_link: StudyLink) -> str:
    if study_link.short_link_domain:
        return f"https://{study_link.short_link_domain}{study_link.url_path}"
    return f"https://merism.test{study_link.url_path}"


def _system_template(channel_type: str) -> MessageTemplate:
    template, _ = MessageTemplate.objects.get_or_create(
        team=None,
        is_system=True,
        channel_type=channel_type,
        name="AI-generated recruitment message",
        defaults={"content": "{{study_name}}\n{{study_link}}"},
    )
    return template


@transaction.atomic
def _create_broadcast(
    *,
    study: Study,
    study_link: StudyLink,
    channel: ChannelConfig,
    targets: list[ChannelTarget],
    message: Any,
) -> RecruitmentBroadcast:
    template = _system_template(channel.channel_type)
    broadcast = RecruitmentBroadcast.objects.create(
        team=study.team,
        study=study,
        study_link=study_link,
        channel=channel,
        template=template,
        status=RecruitmentBroadcast.Status.APPROVED,
        approved_snapshot={
            "title": message.title,
            "template_content": message.body_markdown,
            "body_markdown": message.body_markdown,
            "body_text": message.body_text,
            "msg_format": "markdown",
            "generated_by": "merism.memai.agents.recruitment_message",
        },
        counters={
            "total": len(targets),
            "sent": 0,
            "failed": 0,
            "pending": len(targets),
        },
    )
    DeliveryRecord.objects.bulk_create(
        [
            DeliveryRecord(
                team=study.team,
                broadcast=broadcast,
                recipient_id=target.recipient_id,
                recipient_kind=target.recipient_kind,
                status=DeliveryRecord.Status.PENDING,
            )
            for target in targets
        ]
    )
    return broadcast


def _enqueue_broadcast(broadcast: RecruitmentBroadcast) -> None:
    from merism.recruitment.tasks import dispatch_recruitment_delivery

    dispatch_recruitment_delivery.delay(str(broadcast.id))
