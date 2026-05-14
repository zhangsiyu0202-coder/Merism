"""Link funnel analysis service.

Computes the conversion funnel for a study's links:
  delivery → click → consent → session → completed

Each stage count is derived from the authoritative models, not counters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db.models import Count, Q

from merism.models import (
    DeliveryRecord,
    InterviewSession,
    LinkClick,
    Participation,
    StudyLink,
)

if TYPE_CHECKING:
    from merism.models import Study


@dataclass
class FunnelStage:
    name: str
    count: int
    rate: float  # conversion rate from previous stage (0.0–1.0)


@dataclass
class LinkFunnel:
    study_link_id: str
    slug: str
    stages: list[FunnelStage]
    total_clicks: int
    unique_clicks: int


def compute_link_funnel(study: Study) -> list[LinkFunnel]:
    """Compute funnel for each active StudyLink of a study."""
    links = StudyLink.objects.filter(study=study).order_by("-created_at")
    results = []
    for link in links:
        results.append(_funnel_for_link(link))
    return results


def compute_study_funnel(study: Study) -> list[FunnelStage]:
    """Aggregate funnel across all links for a study."""
    delivered = DeliveryRecord.objects.filter(
        broadcast__study=study,
        status__in=["sent", "delivered"],
    ).count()

    clicked = LinkClick.objects.filter(
        study_link__study=study,
    ).count()

    consented = Participation.objects.filter(
        study=study,
        is_preview=False,
        consented_at__isnull=False,
    ).count()

    sessions = InterviewSession.objects.filter(
        study=study,
        status__in=["active", "completed"],
    ).count()

    completed = Participation.objects.filter(
        study=study,
        is_preview=False,
        status="completed",
    ).count()

    stages = _build_stages(delivered, clicked, consented, sessions, completed)
    return stages


def _funnel_for_link(link: StudyLink) -> LinkFunnel:
    """Compute funnel for a single StudyLink."""
    total_clicks = LinkClick.objects.filter(study_link=link).count()
    unique_clicks = (
        LinkClick.objects.filter(study_link=link)
        .values("identity_hash")
        .distinct()
        .count()
    )

    # Deliveries that reference this link's broadcasts
    delivered = DeliveryRecord.objects.filter(
        broadcast__study_link=link,
        status__in=["sent", "delivered"],
    ).count()

    consented = Participation.objects.filter(
        study=link.study,
        is_preview=False,
        consented_at__isnull=False,
    ).count()

    sessions = InterviewSession.objects.filter(
        study=link.study,
        status__in=["active", "completed"],
    ).count()

    completed = Participation.objects.filter(
        study=link.study,
        is_preview=False,
        status="completed",
    ).count()

    stages = _build_stages(delivered, total_clicks, consented, sessions, completed)

    return LinkFunnel(
        study_link_id=str(link.id),
        slug=link.slug,
        stages=stages,
        total_clicks=total_clicks,
        unique_clicks=unique_clicks,
    )


def _build_stages(
    delivered: int, clicked: int, consented: int, sessions: int, completed: int
) -> list[FunnelStage]:
    """Build ordered funnel stages with conversion rates."""

    def _rate(current: int, previous: int) -> float:
        return round(current / previous, 4) if previous > 0 else 0.0

    return [
        FunnelStage(name="delivered", count=delivered, rate=1.0),
        FunnelStage(name="clicked", count=clicked, rate=_rate(clicked, delivered)),
        FunnelStage(name="consented", count=consented, rate=_rate(consented, clicked)),
        FunnelStage(name="session_started", count=sessions, rate=_rate(sessions, consented)),
        FunnelStage(name="completed", count=completed, rate=_rate(completed, sessions)),
    ]


def click_stats_for_link(link: StudyLink) -> dict:
    """Aggregate click stats for a single link (for API)."""
    qs = LinkClick.objects.filter(study_link=link)
    total = qs.count()
    by_trigger = dict(qs.values_list("trigger").annotate(c=Count("id")).values_list("trigger", "c"))
    by_device = dict(qs.values_list("device_type").annotate(c=Count("id")).values_list("device_type", "c"))
    by_source = dict(
        qs.exclude(utm_source="")
        .values_list("utm_source")
        .annotate(c=Count("id"))
        .values_list("utm_source", "c")
    )
    top_referers = list(
        qs.exclude(referer="")
        .values("referer")
        .annotate(c=Count("id"))
        .order_by("-c")[:10]
    )
    return {
        "total_clicks": total,
        "unique_clicks": qs.values("identity_hash").distinct().count(),
        "by_trigger": by_trigger,
        "by_device": by_device,
        "by_source": by_source,
        "top_referers": top_referers,
    }
