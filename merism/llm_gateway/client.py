"""Central entry point for AI service clients.

All business code calls :func:`get_client` to obtain a configured client.
Resolution: Team's ServiceSettings → env-var fallback.

Usage::

    from merism.llm_gateway.client import get_client

    client = await get_client("chat", team=team, trace_id=trace_id)
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from merism.models.team import Team

logger = logging.getLogger(__name__)

_LOGICAL_TO_SERVICE = {
    "chat": "llm",
    "reasoner": "llm",
    "vision": "llm",
    "embedding": "embedding",
    "asr_realtime": "stt",
    "tts_realtime": "tts",
    "omni_realtime": "llm",
}


async def get_client(
    logical_name: str,
    *,
    team: Team,
    trace_id: UUID,
) -> Any:
    """Return a configured AI service client for the given logical capability."""
    client = _from_service_settings(logical_name, team)
    if client is not None:
        return client

    # Env-var fallback for LLM-type requests
    if _LOGICAL_TO_SERVICE.get(logical_name) in ("llm", "embedding"):
        from merism.memai.llm import get_llm
        return get_llm(async_=True)

    from merism.llm_gateway.exceptions import RouteNotFoundError
    raise RouteNotFoundError(logical_name, str(team.id))


def sync_get_client(
    logical_name: str,
    *,
    team: Team,
    trace_id: UUID,
) -> Any:
    """Synchronous version of :func:`get_client`."""
    client = _from_service_settings(logical_name, team)
    if client is not None:
        return client

    if _LOGICAL_TO_SERVICE.get(logical_name) in ("llm", "embedding"):
        from merism.memai.llm import get_llm
        return get_llm(async_=False)

    from merism.llm_gateway.exceptions import RouteNotFoundError
    raise RouteNotFoundError(logical_name, str(team.id))


def _from_service_settings(logical_name: str, team: Team) -> Any | None:
    """Build client from team's ServiceSettings."""
    from merism.models.service_settings import ServiceSettings
    from merism.services.configuration.factory import (
        create_embedding_service,
        create_llm_service,
        create_stt_service,
        create_tts_service,
    )

    try:
        ss = ServiceSettings.objects.get(team=team)
    except ServiceSettings.DoesNotExist:
        return None

    service_type = _LOGICAL_TO_SERVICE.get(logical_name)

    if service_type == "llm":
        config = ss.get_llm_config()
        if config:
            return create_llm_service(config, async_=("sync" not in logical_name))
    elif service_type == "embedding":
        config = ss.get_embedding_config()
        if config:
            return create_embedding_service(config)
    elif service_type == "tts":
        config = ss.get_tts_config()
        if config:
            return create_tts_service(config)
    elif service_type == "stt":
        config = ss.get_stt_config()
        if config:
            return create_stt_service(config)

    return None


__all__ = ["get_client", "sync_get_client"]
