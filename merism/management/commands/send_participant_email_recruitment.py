from __future__ import annotations

import os

from django.core.management.base import BaseCommand, CommandError

from merism.models import Study
from merism.recruitment.participant_email_recruitment import (
    EmailSenderConfig,
    launch_participant_email_recruitment,
)


class Command(BaseCommand):
    help = "Use AI to email Participant.email recipients for a study via one SMTP sender."

    def add_arguments(self, parser) -> None:  # type: ignore[override]
        parser.add_argument("study_id", help="Study UUID")
        parser.add_argument("--limit", type=int, default=None, help="Max recipients to queue")

    def handle(self, *args: object, **options: object) -> None:
        study_id = str(options["study_id"])
        limit = options.get("limit")
        try:
            study = Study.objects.select_related("team").get(id=study_id)
        except Study.DoesNotExist as exc:
            raise CommandError(f"Study {study_id} does not exist.") from exc

        sender_config = _sender_config_from_env()
        result = launch_participant_email_recruitment(
            study=study,
            sender_config=sender_config,
            limit=limit,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Queued email broadcast {result.broadcast_id} to "
                f"{result.recipient_count} participant emails."
            )
        )


def _sender_config_from_env() -> EmailSenderConfig:
    host = os.environ.get("MERISM_OUTBOUND_EMAIL_HOST", "").strip()
    username = os.environ.get("MERISM_OUTBOUND_EMAIL_USERNAME", "").strip()
    password = os.environ.get("MERISM_OUTBOUND_EMAIL_PASSWORD", "")
    from_address = os.environ.get("MERISM_OUTBOUND_EMAIL_FROM", "").strip()
    port = int(os.environ.get("MERISM_OUTBOUND_EMAIL_PORT", "587"))
    use_tls = os.environ.get("MERISM_OUTBOUND_EMAIL_USE_TLS", "1") != "0"
    reply_to = os.environ.get("MERISM_OUTBOUND_EMAIL_REPLY_TO", "").strip()

    missing = [
        name
        for name, value in (
            ("MERISM_OUTBOUND_EMAIL_HOST", host),
            ("MERISM_OUTBOUND_EMAIL_USERNAME", username),
            ("MERISM_OUTBOUND_EMAIL_PASSWORD", password),
            ("MERISM_OUTBOUND_EMAIL_FROM", from_address),
        )
        if not value
    ]
    if missing:
        raise CommandError(f"Missing required email env var(s): {', '.join(missing)}")

    return EmailSenderConfig(
        host=host,
        port=port,
        use_tls=use_tls,
        username=username,
        password=password,
        from_address=from_address,
        reply_to=reply_to,
    )
