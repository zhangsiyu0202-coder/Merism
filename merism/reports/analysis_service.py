"""Study-level analytics aggregator.

Pure function that turns a study's SessionQuote + SessionInsight rows
into a compact dict the frontend AnalysisTab renders charts + KPIs
from. One DB read path, no LLM calls. Called by the
``/api/studies/:id/analysis/`` endpoint.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any

from django.db.models import Count, Sum
from django.utils import timezone

from merism.models import (
    InterviewSession,
    SessionInsight,
    SessionQuote,
    Study,
)


def compute_study_aggregate(study: Study) -> dict[str, Any]:
    """Return an aggregate analysis payload for one study."""
    quotes_qs = SessionQuote.objects.filter(study=study)
    sessions_qs = InterviewSession.objects.filter(study=study)
    insights_qs = SessionInsight.objects.filter(session__study=study)

    quote_count = quotes_qs.count()
    session_count = sessions_qs.count()
    completed_count = sessions_qs.filter(
        status=InterviewSession.Status.COMPLETED
    ).count()
    insight_count = insights_qs.count()

    # Talk time (hours) for completed sessions.
    talk_time_hours = _talk_time_hours(sessions_qs)

    # ── Theme / code counts (deductive only) ─────────────
    theme_counts: Counter = Counter()
    sentiment_counts: Counter = Counter()
    action_counts: Counter = Counter()
    sentiment_over_time: dict[str, Counter] = defaultdict(Counter)

    for quote in quotes_qs.values(
        "tags", "ts_start_ms", "created_at", "session_id"
    ):
        tags = quote.get("tags") or {}
        for m in tags.get("deductive", []) or []:
            theme_counts[m.get("code_id", "")] += 1
        if s := tags.get("sentiment"):
            sentiment_counts[s] += 1
            # Bucket by date for trend chart.
            day = quote["created_at"].date().isoformat()
            sentiment_over_time[day][s] += 1
        if a := tags.get("action_type"):
            action_counts[a] += 1

    # Resolve code_id → display name via the codebook.
    codebook = {
        c["code_id"]: c for c in (study.codebook or [])
    }
    top_themes = [
        {
            "code_id": code,
            "name": codebook.get(code, {}).get("name", code),
            "count": count,
            "description": codebook.get(code, {}).get("description", ""),
        }
        for code, count in theme_counts.most_common(10)
    ]

    # ── Top extracted tasks across sessions ─────────────
    task_buckets: list[dict[str, Any]] = []
    for insight in insights_qs.values("extracted_tasks", "session_id"):
        for task in insight.get("extracted_tasks") or []:
            task_buckets.append(
                {
                    **task,
                    "session_id": str(insight["session_id"]),
                }
            )
    # Sort: P0 first, then P1, then P2.
    priority_rank = {"P0": 0, "P1": 1, "P2": 2}
    task_buckets.sort(key=lambda t: priority_rank.get(t.get("priority", "P2"), 3))
    top_tasks = task_buckets[:12]

    # ── Sentiment trend → day-sorted list ───────────────
    trend = sorted(
        [
            {
                "date": day,
                "positive": counts.get("positive", 0),
                "negative": counts.get("negative", 0),
                "neutral": counts.get("neutral", 0),
                "mixed": counts.get("mixed", 0),
            }
            for day, counts in sentiment_over_time.items()
        ],
        key=lambda d: d["date"],
    )

    return {
        "study_id": str(study.id),
        "kpi": {
            "session_count": session_count,
            "session_completed": completed_count,
            "quote_count": quote_count,
            "insight_count": insight_count,
            "theme_count": len(theme_counts),
            "talk_time_hours": talk_time_hours,
        },
        "top_themes": top_themes,
        "sentiment_distribution": dict(sentiment_counts),
        "action_distribution": dict(action_counts),
        "sentiment_over_time": trend,
        "top_tasks": top_tasks,
        "codebook_size": len(study.codebook or []),
    }


def _talk_time_hours(sessions_qs) -> float:
    from django.db.models import DurationField, ExpressionWrapper, F

    duration_expr = ExpressionWrapper(
        F("ended_at") - F("started_at"),
        output_field=DurationField(),
    )
    total: timedelta | None = (
        sessions_qs.filter(
            status=InterviewSession.Status.COMPLETED,
            started_at__isnull=False,
            ended_at__isnull=False,
        )
        .annotate(dur=duration_expr)
        .aggregate(total=Sum("dur"))
        .get("total")
    )
    if total is None:
        return 0.0
    return round(total.total_seconds() / 3600, 1)
