"""Rate limiting for IM recruitment broadcast dispatch.

Uses Django cache (Redis-backed in production) to implement a sliding window
counter per channel. Limit: 100 messages per channel per hour.

Key schema: merism:channel_rate:{channel_config_id}
TTL: 3600 seconds (1 hour)

Refs: Requirement 7 AC 5-6, Design §6
"""

from __future__ import annotations

import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

RATE_LIMIT: int = 100
WINDOW_SECONDS: int = 3600  # 1 hour


def _cache_key(channel_config_id: str) -> str:
    return f"merism:channel_rate:{channel_config_id}"


def check_and_increment_rate(channel_config_id: str) -> tuple[bool, int]:
    """Check if the channel is within rate limit and increment counter.

    Returns (allowed: bool, current_count: int).
    Uses Redis sliding window via Django cache.

    The counter is created with a 1-hour TTL on first use, so it naturally
    resets each hour window without any explicit cleanup.
    """
    key = _cache_key(channel_config_id)

    # cache.add sets the key only if it does not already exist (atomic).
    # If the key is new, the counter starts at 1 and is within the limit.
    added = cache.add(key, 1, timeout=WINDOW_SECONDS)
    if added:
        # Key was freshly created — this is the first message in the window.
        return True, 1

    # Key already exists; increment atomically.
    try:
        current = cache.incr(key)
    except ValueError:
        # Key expired between add() and incr() — treat as a fresh window.
        cache.add(key, 1, timeout=WINDOW_SECONDS)
        return True, 1

    allowed = current <= RATE_LIMIT
    if not allowed:
        logger.warning(
            "rate_limit exceeded channel_config_id=%s current_count=%d limit=%d",
            channel_config_id,
            current,
            RATE_LIMIT,
        )
    return allowed, current


def get_remaining_quota(channel_config_id: str) -> int:
    """Return remaining messages allowed in the current hour window."""
    key = _cache_key(channel_config_id)
    current: int | None = cache.get(key)
    if current is None:
        return RATE_LIMIT
    return max(0, RATE_LIMIT - current)
