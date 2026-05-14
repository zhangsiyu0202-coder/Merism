"""Recruitment Celery tasks.

Three tasks:

1. :func:`dispatch_recruitment_delivery` — send one broadcast's messages.
2. :func:`retry_failed_deliveries` — re-queue failed `DeliveryRecord`s.
3. :func:`health_check_channels` — periodic beat task (every 30 min per
   spec Req 5.1).

All three route through the vendored adapters in
:mod:`merism.recruitment.adapters`.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from celery import shared_task
from django.db import transaction

from merism.models import (
    ChannelConfig,
    ChannelHealthCheck,
    DeliveryRecord,
    RecruitmentBroadcast,
)
from merism.recruitment import decrypt_credentials, get_adapter
from merism.recruitment.adapters.base import IMMessage
from merism.recruitment.rate_limit import check_and_increment_rate
from merism.recruitment.renderer import render_template

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def dispatch_recruitment_delivery(self, broadcast_id: str) -> dict[str, Any]:
    """Send every pending DeliveryRecord for ``broadcast_id``.

    Skips if the broadcast is already in a terminal state. Respects the
    per-channel rate limit — if the limit is reached, remaining deliveries
    stay ``pending`` and are picked up by the next dispatch attempt.

    Returns a counters dict ``{sent, failed, pending}`` for observability.
    """
    try:
        broadcast = RecruitmentBroadcast.objects.select_related("channel", "template").get(
            id=broadcast_id
        )
    except RecruitmentBroadcast.DoesNotExist:
        logger.warning("recruit.dispatch.broadcast_missing", extra={"broadcast_id": broadcast_id})
        return {"skipped": True}

    if broadcast.status in (
        RecruitmentBroadcast.Status.COMPLETED,
        RecruitmentBroadcast.Status.FAILED,
    ):
        return {"skipped": True, "status": broadcast.status}

    try:
        creds = decrypt_credentials(broadcast.channel.credentials_encrypted)
        adapter = get_adapter(broadcast.channel.channel_type, creds)
    except Exception as exc:  # pragma: no cover - exercised via mocks
        logger.exception("recruit.dispatch.adapter_init_failed")
        broadcast.status = RecruitmentBroadcast.Status.FAILED
        broadcast.save(update_fields=["status", "updated_at"])
        raise self.retry(exc=exc, countdown=60) from exc

    counters = {"sent": 0, "failed": 0, "pending": 0}
    pending_qs = DeliveryRecord.objects.filter(
        broadcast=broadcast, status=DeliveryRecord.Status.PENDING
    ).order_by("created_at")

    for delivery in pending_qs:
        allowed, _remaining = check_and_increment_rate(str(broadcast.channel_id))
        if not allowed:
            counters["pending"] += 1
            continue

        snapshot = broadcast.approved_snapshot or {}
        rendered_text, _missing = render_template(
            snapshot.get("template_content") or broadcast.template.content,
            context=_delivery_context(broadcast, delivery),
        )
        message = IMMessage(
            content=rendered_text,
            msg_type=snapshot.get("msg_format") or "markdown",
            extra=_message_extra(snapshot),
        )
        try:
            if delivery.recipient_kind == "group":
                result = adapter.send_to_group(delivery.recipient_id, message)
            else:
                result = adapter.send_message(delivery.recipient_id, message)
        except Exception as exc:
            delivery.status = DeliveryRecord.Status.FAILED
            delivery.error = str(exc)[:500]
            delivery.retry_count += 1
            delivery.save()
            counters["failed"] += 1
            continue

        if result.success:
            delivery.status = DeliveryRecord.Status.SENT
            delivery.message_id = result.message_id or ""
            delivery.sent_at = datetime.now(UTC)
            counters["sent"] += 1
            # Propagate delivery success to the recipient's Invitation.
            if delivery.trace_id:
                from merism.models import Invitation
                Invitation.objects.filter(trace_id=delivery.trace_id).update(
                    status=Invitation.Status.DELIVERED,
                    delivered_at=delivery.sent_at,
                )
        else:
            delivery.status = DeliveryRecord.Status.FAILED
            delivery.error = (result.error or "")[:500]
            delivery.retry_count += 1
            counters["failed"] += 1
        delivery.save()

    _finalize_broadcast_status(broadcast, counters)
    return counters


def _delivery_context(
    broadcast: RecruitmentBroadcast, delivery: DeliveryRecord
) -> dict[str, Any]:
    """Build the context dict used by the template renderer.

    Side effect: create (or reuse) an Invitation for this recipient and
    stamp the delivery + invitation with a shared ``trace_id`` so the
    funnel can be cross-joined later. The participant URL embeds the
    invitation token (``?t=``) whenever the study link requires it, so
    a forwarded link still funnels back to a specific recipient.
    """
    from merism.models import Invitation
    from merism.models.invitation import hash_recipient

    study_link = broadcast.study_link
    link_url = ""
    invitation: Invitation | None = None

    if study_link is not None and delivery.recipient_kind != "group":
        rh = hash_recipient(delivery.recipient_id)
        invitation, _ = Invitation.objects.get_or_create(
            study_link=study_link,
            recipient_hash=rh,
            defaults={
                "team": broadcast.team,
                "recipient_display": delivery.recipient_id[:200],
            },
        )
        # Stamp delivery with the invitation's trace_id so the funnel joins.
        if delivery.trace_id != invitation.trace_id:
            delivery.trace_id = invitation.trace_id
            delivery.save(update_fields=["trace_id"])

        base = f"https://merism.test{study_link.url_path}"
        # Always include the token — harmless on open links, required on
        # closed ones. Researchers don't need to know the difference.
        link_url = f"{base}?t={invitation.token}"
    elif study_link is not None:
        base = f"https://merism.test{study_link.url_path}"
        link_url = base

    return {
        "study_name": broadcast.study.name or broadcast.study.research_goal[:60],
        "study_link": link_url,
        "delivery_id": str(delivery.id),
        "recipient_id": delivery.recipient_id,
        "invitation_token": invitation.token if invitation else "",
    }


def _finalize_broadcast_status(
    broadcast: RecruitmentBroadcast, counters: dict[str, int]
) -> None:
    total = DeliveryRecord.objects.filter(broadcast=broadcast).count()
    failed_count = DeliveryRecord.objects.filter(
        broadcast=broadcast, status=DeliveryRecord.Status.FAILED
    ).count()
    sent_count = DeliveryRecord.objects.filter(
        broadcast=broadcast, status__in=[DeliveryRecord.Status.SENT, DeliveryRecord.Status.DELIVERED]
    ).count()

    if sent_count + failed_count >= total:
        if failed_count == 0:
            new_status = RecruitmentBroadcast.Status.COMPLETED
        elif sent_count == 0:
            new_status = RecruitmentBroadcast.Status.FAILED
        else:
            new_status = RecruitmentBroadcast.Status.PARTIALLY_FAILED
    else:
        new_status = RecruitmentBroadcast.Status.SENDING

    broadcast.counters = {
        "total": total,
        "sent": sent_count,
        "failed": failed_count,
        "pending": max(0, total - sent_count - failed_count),
    }
    broadcast.status = new_status
    broadcast.save(update_fields=["counters", "status", "updated_at"])


def _message_extra(snapshot: dict[str, Any]) -> dict[str, Any]:
    extra: dict[str, Any] = {}
    title = snapshot.get("title")
    if isinstance(title, str) and title.strip():
        extra["subject"] = title.strip()
    body_text = snapshot.get("body_text")
    if isinstance(body_text, str) and body_text.strip():
        extra["text_alt"] = body_text
    return extra


@shared_task
def retry_failed_deliveries(broadcast_id: str) -> dict[str, Any]:
    """Reset every failed delivery to pending and re-enqueue dispatch."""
    with transaction.atomic():
        updated = DeliveryRecord.objects.filter(
            broadcast_id=broadcast_id, status=DeliveryRecord.Status.FAILED
        ).update(status=DeliveryRecord.Status.PENDING, error="")
    if updated:
        dispatch_recruitment_delivery.delay(str(broadcast_id))
    return {"reset": updated}


@shared_task
def health_check_channels() -> dict[str, Any]:
    """Periodic beat task (every 30 min).

    For each active channel, call adapter.health_check() and log the
    outcome. Flip channel status to ``error`` after 2 consecutive failures
    (per spec Req 5.4).
    """
    checked = {"ok": 0, "error": 0}
    for channel in ChannelConfig.objects.filter(status__in=[
        ChannelConfig.Status.ACTIVE,
        ChannelConfig.Status.ERROR,
    ]):
        try:
            creds = decrypt_credentials(channel.credentials_encrypted)
            adapter = get_adapter(channel.channel_type, creds)
            ok, err = adapter.health_check()
        except Exception as exc:  # pragma: no cover
            ok, err = False, str(exc)

        ChannelHealthCheck.objects.create(
            team=channel.team,
            channel=channel,
            ok=ok,
            error=err or "",
        )

        if ok:
            channel.status = ChannelConfig.Status.ACTIVE
            channel.consecutive_failures = 0
            channel.last_error = ""
            channel.last_healthy_at = datetime.now(UTC)
            checked["ok"] += 1
        else:
            channel.consecutive_failures = (channel.consecutive_failures or 0) + 1
            channel.last_error = (err or "health check failed")[:500]
            if channel.consecutive_failures >= 2:
                channel.status = ChannelConfig.Status.ERROR
            checked["error"] += 1
        channel.save()
    return checked


@shared_task
def dispatch_pending_broadcasts() -> dict[str, int]:
    """Catch-up scheduler: find APPROVED broadcasts that have no
    in-flight dispatch and enqueue ``dispatch_recruitment_delivery``
    for each.

    Why not rely purely on the admin-action enqueue
    (``RecruitmentBroadcast.admin_approve``)? If the web dyno or the
    approving user's request dies after DB commit but before ``.delay()``,
    the broadcast is stranded. This periodic task is the recovery loop.
    It is idempotent: ``dispatch_recruitment_delivery`` returns a
    ``{"skipped": True}`` result when the broadcast is already COMPLETED
    or FAILED, and the SENDING → SENDING transition collapses into the
    same run because pending deliveries are the unit of work.
    """
    from merism.models import RecruitmentBroadcast

    queryset = RecruitmentBroadcast.objects.filter(
        status__in=[
            RecruitmentBroadcast.Status.APPROVED,
            RecruitmentBroadcast.Status.SENDING,
        ]
    )
    enqueued = 0
    for broadcast in queryset.only("id"):
        try:
            dispatch_recruitment_delivery.delay(str(broadcast.id))
            enqueued += 1
        except Exception:
            logger.exception(
                "recruit.catch_up.enqueue_failed",
                extra={"broadcast_id": str(broadcast.id)},
            )
    logger.info("recruit.catch_up.run", extra={"enqueued": enqueued})
    return {"enqueued": enqueued}
