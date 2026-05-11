"""Central entry point for the LLM Gateway.

All business code should call :func:`get_client` to obtain a configured
client for a given logical capability. The function resolves the team's
route, decrypts credentials, checks budget, and returns the appropriate
client object (LiteLLMClient for HTTP, ParaformerClient for ASR, etc.).

Usage::

    from merism.llm_gateway.client import get_client

    # HTTP (chat / reasoner / vision / embedding)
    client = await get_client("chat", team=team, trace_id=trace_id)
    async for chunk in client.stream(messages=[...]):
        ...

    # WebSocket realtime (ASR / TTS)
    stt = await get_client("asr_realtime", team=team, trace_id=trace_id)
    async for event in stt.stream_stt(audio_stream):
        ...
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from merism.llm_gateway.exceptions import (
    BudgetExceededError,
    ProviderUnavailableError,
    RouteNotFoundError,
)
from merism.llm_gateway.litellm_client import LiteLLMClient
from merism.models.llm_gateway import LLMBudget, LLMProvider, LLMRoute
from merism.models.team import Team
from merism.recruitment.crypto import decrypt_credentials

logger = logging.getLogger(__name__)


async def get_client(
    logical_name: str,
    *,
    team: Team,
    trace_id: UUID,
) -> Any:
    """Resolve a route and return a configured client.

    For HTTP-protocol providers (chat/reasoner/vision/embedding), returns
    a :class:`~merism.llm_gateway.litellm_client.LiteLLMClient`.

    For WS-protocol providers (asr_realtime/tts_realtime/omni_realtime),
    returns the appropriate realtime client (ParaformerClient /
    CosyVoiceClient) with credentials injected from the DB.

    Raises:
        RouteNotFoundError: No route configured for this team + logical_name.
        ProviderUnavailableError: The resolved provider is inactive.
        BudgetExceededError: Team exceeded hard budget limit (only when
            hard_limit_action == "block").
    """
    # 1. Resolve route
    route = await _resolve_route(logical_name, team)

    # 2. Check provider active
    provider = route.primary
    if not provider.is_active:
        raise ProviderUnavailableError(
            f"Provider '{provider.display_name}' is inactive. "
            f"Re-enable it or change the route for '{logical_name}'."
        )

    # 3. Budget check (non-blocking for alert_only / degrade)
    await _check_budget(team, logical_name)

    # 4. Build client based on protocol
    fallback_provider = route.fallback if route.fallback and route.fallback.is_active else None

    if provider.protocol == LLMProvider.Protocol.HTTP:
        return LiteLLMClient(
            provider=provider,
            route=route,
            trace_id=trace_id,
            fallback_provider=fallback_provider,
        )
    elif provider.protocol == LLMProvider.Protocol.WS:
        return _build_ws_client(logical_name, provider)
    else:
        raise ProviderUnavailableError(f"Unknown protocol: {provider.protocol}")


async def _resolve_route(logical_name: str, team: Team) -> LLMRoute:
    """Look up the team's route, with select_related for FK access."""
    try:
        return await (
            LLMRoute.objects.select_related("primary", "fallback")
            .aget(team=team, logical_name=logical_name)
        )
    except LLMRoute.DoesNotExist:
        raise RouteNotFoundError(logical_name, str(team.id))


async def _check_budget(team: Team, logical_name: str) -> None:
    """Check if team is over hard budget limit.

    Only raises when hard_limit_action == "block". For "alert_only" and
    "degrade", we log a warning but don't block.
    """
    import datetime

    period = datetime.date.today().strftime("%Y-%m")
    try:
        budget = await LLMBudget.objects.aget(team=team, period=period)
    except LLMBudget.DoesNotExist:
        return  # No budget configured = unlimited

    if budget.is_over_hard_limit:
        if budget.hard_limit_action == LLMBudget.Action.BLOCK:
            raise BudgetExceededError(
                team_id=str(team.id),
                period=period,
                spent=float(budget.current_spent_usd),
                cap=float(budget.monthly_cap_usd),
            )
        else:
            logger.warning(
                "llm_gateway.budget_exceeded: team=%s period=%s spent=%.2f cap=%.2f action=%s logical=%s",
                str(team.id), period, float(budget.current_spent_usd),
                float(budget.monthly_cap_usd), budget.hard_limit_action, logical_name,
            )


def _build_ws_client(logical_name: str, provider: LLMProvider) -> Any:
    """Instantiate the correct WS realtime client with provider credentials."""
    creds = decrypt_credentials(provider.credentials_encrypted)
    api_key = creds.get("api_key", "")
    url = provider.base_url
    model = provider.model

    if logical_name == "asr_realtime":
        from merism.stt import ParaformerClient

        return ParaformerClient(api_key=api_key, model=model, url=url)
    elif logical_name == "tts_realtime":
        from merism.tts import CosyVoiceClient

        return CosyVoiceClient(api_key=api_key, model=model, url=url)
    elif logical_name == "omni_realtime":
        # Omni uses the same WS protocol as ASR but with a different model
        # that handles both input audio and output audio in one session.
        # For now, return a ParaformerClient-like object; when the omni
        # adapter diverges, we'll add an OmniRealtimeClient class.
        from merism.stt import ParaformerClient

        return ParaformerClient(api_key=api_key, model=model, url=url)
    else:
        raise ProviderUnavailableError(f"No WS client for logical_name='{logical_name}'")


def sync_get_client(
    logical_name: str,
    *,
    team: Team,
    trace_id: UUID,
) -> Any:
    """Synchronous wrapper around :func:`get_client`.

    For use in sync contexts (Celery tasks, sync views, management commands).
    Blocks the calling thread until the async resolution completes.
    """
    from asgiref.sync import async_to_sync

    return async_to_sync(get_client)(logical_name, team=team, trace_id=trace_id)


__all__ = ["get_client", "sync_get_client"]
