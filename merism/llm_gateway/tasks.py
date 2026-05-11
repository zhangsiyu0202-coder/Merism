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

    Returns Decimal or None if Langfuse is not configured / unreachable.

    TODO: Implement once Langfuse Cloud keys are provisioned. The API
    endpoint is GET /api/public/metrics/daily with filter on
    metadata.team_id and date range for the period.
    """
    from decimal import Decimal

    from django.conf import settings

    if not settings.LANGFUSE_PUBLIC_KEY:
        return None

    # Placeholder — return None until Langfuse API integration is wired.
    # When implemented:
    #   1. GET https://{LANGFUSE_HOST}/api/public/metrics/daily
    #      ?traceName=*&metadata.team_id={team_id}&fromTimestamp=...&toTimestamp=...
    #   2. Sum totalCost across all days in the response
    #   3. Return as Decimal
    return None
