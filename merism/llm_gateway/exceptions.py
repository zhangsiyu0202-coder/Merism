"""LLM Gateway exceptions."""

from __future__ import annotations


class GatewayError(Exception):
    """Base for all LLM Gateway errors."""


class ProviderUnavailableError(GatewayError):
    """The selected provider is inactive or unreachable."""


class BudgetExceededError(GatewayError):
    """Team has exceeded its monthly LLM budget."""

    def __init__(self, team_id: str, period: str, spent: float, cap: float) -> None:
        self.team_id = team_id
        self.period = period
        self.spent = spent
        self.cap = cap
        super().__init__(f"Team {team_id} exceeded budget for {period}: ${spent:.2f} / ${cap:.2f}")


class RouteNotFoundError(GatewayError):
    """No LLMRoute configured for the requested logical_name + team."""

    def __init__(self, logical_name: str, team_id: str) -> None:
        self.logical_name = logical_name
        self.team_id = team_id
        super().__init__(f"No route for '{logical_name}' on team {team_id}")
