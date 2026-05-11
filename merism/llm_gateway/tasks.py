"""LLM Gateway Celery tasks.

Currently contains the budget reconciliation task that syncs spend data
from Langfuse into ``LLMBudget.current_spent_usd``.
"""

from __future__ import annotations

import datetime
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="merism.llm_gateway.tasks.reconcile_budgets")
def reconcile_budgets() -> int:
    """Reconcile LLM budget spend from Langfuse for the current period.

    Runs hourly via Celery beat. For each team with an active budget for
    the current month, queries Langfuse's cost aggregation and updates
    ``LLMBudget.current_spent_usd``.

    Returns the number of budgets updated.

    NOTE: First release uses alert_only as default action, so even if
    reconciliation lags, no requests are blocked. The task is
    best-effort — if Langfuse is unreachable, we log and skip.
    """
    from merism.models.llm_gateway import LLMBudget

    period = datetime.date.today().strftime("%Y-%m")
    budgets = LLMBudget.objects.filter(period=period)
    updated = 0

    for budget in budgets:
        try:
            spent = _fetch_spend_from_langfuse(budget.team_id, period)
            if spent is not None:
                budget.current_spent_usd = spent
                budget.save(update_fields=["current_spent_usd", "updated_at"])
                updated += 1

                if budget.is_over_soft_limit:
                    logger.warning(
                        "llm_gateway.budget.soft_limit_reached",
                        team_id=str(budget.team_id),
                        period=period,
                        spent=float(spent),
                        cap=float(budget.monthly_cap_usd),
                    )
        except Exception:
            logger.exception(
                "llm_gateway.budget.reconcile_failed",
                team_id=str(budget.team_id),
                period=period,
            )

    logger.info("llm_gateway.budget.reconcile_done", updated=updated, period=period)
    return updated


def _fetch_spend_from_langfuse(team_id, period: str):
    """Query Langfuse for total USD spend for a team in a given month.

    Uses the ``GET /api/public/metrics/daily`` endpoint filtered by
    ``metadata.team_id``. Returns Decimal or None if Langfuse is not
    configured or the API call fails.
    """
    from decimal import Decimal

    import httpx
    from django.conf import settings

    public_key = getattr(settings, "LANGFUSE_PUBLIC_KEY", "")
    secret_key = getattr(settings, "LANGFUSE_SECRET_KEY", "")
    host = getattr(settings, "LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not public_key or not secret_key:
        return None

    # Period is "YYYY-MM" — compute first/last day
    year, month = int(period[:4]), int(period[5:7])
    from_date = f"{period}-01"
    # Last day: next month's first day
    if month == 12:
        to_date = f"{year + 1}-01-01"
    else:
        to_date = f"{year}-{month + 1:02d}-01"

    url = f"{host.rstrip('/')}/api/public/metrics/daily"
    params = {
        "traceName": None,  # all traces
        "fromTimestamp": f"{from_date}T00:00:00Z",
        "toTimestamp": f"{to_date}T00:00:00Z",
        "tags": f"team_id:{team_id}",
    }
    # Remove None values
    params = {k: v for k, v in params.items() if v is not None}

    try:
        resp = httpx.get(
            url,
            params=params,
            auth=(public_key, secret_key),
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()

        # Response shape: {"data": [{"date": "...", "totalCost": float, ...}]}
        total = sum(day.get("totalCost", 0.0) for day in data.get("data", []))
        return Decimal(str(round(total, 4)))
    except Exception:
        logger.exception(
            "llm_gateway.langfuse_api_failed: team=%s period=%s",
            str(team_id), period,
        )
        return None
