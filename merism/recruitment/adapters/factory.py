from __future__ import annotations

from typing import Any

from merism.recruitment.adapters import (
    CHANNEL_EMAIL,
    CHANNEL_FEISHU,
    CHANNEL_QQ_GROUP,
    CHANNEL_QQ_GUILD,
    CHANNEL_WECOM_BOT,
)
from merism.recruitment.adapters.base import IMChannelBase
from merism.recruitment.adapters.email_adapter import EmailAdapter
from merism.recruitment.adapters.feishu_adapter import FeishuAdapter
from merism.recruitment.adapters.qq_group_adapter import QQGroupAdapter
from merism.recruitment.adapters.qq_guild_adapter import QQGuildAdapter
from merism.recruitment.adapters.wecom_bot_adapter import WecomBotAdapter


def get_adapter(channel_type: str, config: dict[str, Any]) -> IMChannelBase:
    """Return an instantiated IM channel adapter for the given channel_type.

    Args:
        channel_type: One of the CHANNEL_* constants defined in this package.
        config: Credential/configuration dict passed to the adapter's from_config().

    Raises:
        ValueError: If channel_type is not a recognised channel type.
    """
    if channel_type == CHANNEL_FEISHU:
        return FeishuAdapter.from_config(config)
    if channel_type == CHANNEL_WECOM_BOT:
        return WecomBotAdapter.from_config(config)
    if channel_type == CHANNEL_QQ_GUILD:
        return QQGuildAdapter.from_config(config)
    if channel_type == CHANNEL_QQ_GROUP:
        return QQGroupAdapter.from_config(config)
    if channel_type == CHANNEL_EMAIL:
        return EmailAdapter.from_config(config)
    raise ValueError(
        f"Unknown channel type {channel_type!r}. "
        f"Supported types: {CHANNEL_FEISHU!r}, {CHANNEL_WECOM_BOT!r}, "
        f"{CHANNEL_QQ_GUILD!r}, {CHANNEL_QQ_GROUP!r}, {CHANNEL_EMAIL!r}."
    )
