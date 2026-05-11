"""
Send-only IM channel adapters vendored from CowAgent.

This package provides a thin adapter layer for dispatching recruitment
messages over instant-messaging platforms (Feishu, WeCom Bot, QQ Guild Bot,
QQ Group Bot) without pulling in CowAgent's Agent/Bridge/Memory infrastructure.

Public API:

    from merism.recruitment.adapters import (
        CHANNEL_FEISHU,
        CHANNEL_WECOM_BOT,
        CHANNEL_QQ_GUILD,
        CHANNEL_QQ_GROUP,
    )
    from merism.recruitment.adapters.base import (
        IMChannelBase,
        IMMessage,
        SendResult,
    )
    from merism.recruitment.adapters.factory import get_adapter

Package layout:
    base.py               — IMChannelBase, IMMessage, SendResult dataclasses
    feishu_adapter.py     — Feishu Open API adapter (tenant_access_token + send)
    wecom_bot_adapter.py  — WeCom Bot webhook adapter
    qq_guild_adapter.py   — QQ 频道机器人 adapter (Bot appid.token auth)
    qq_group_adapter.py   — QQ 群机器人 adapter (OAuth2 client_credentials)
    factory.py            — get_adapter(channel_type, config) factory function
"""

# Channel type string constants — mirrors ChannelConfig.ChannelType choices
CHANNEL_FEISHU: str = "feishu"
CHANNEL_WECOM_BOT: str = "wecom_bot"
CHANNEL_QQ_GUILD: str = "qq_guild"
CHANNEL_QQ_GROUP: str = "qq_group"
CHANNEL_EMAIL: str = "email"

SUPPORTED_CHANNEL_TYPES: tuple[str, ...] = (
    CHANNEL_FEISHU,
    CHANNEL_WECOM_BOT,
    CHANNEL_QQ_GUILD,
    CHANNEL_QQ_GROUP,
    CHANNEL_EMAIL,
)

# Re-export factory so callers can do:
#   from merism.recruitment.adapters import get_adapter
from merism.recruitment.adapters.factory import get_adapter  # noqa: E402

__all__ = [
    "CHANNEL_FEISHU",
    "CHANNEL_WECOM_BOT",
    "CHANNEL_QQ_GUILD",
    "CHANNEL_QQ_GROUP",
    "CHANNEL_EMAIL",
    "SUPPORTED_CHANNEL_TYPES",
    "get_adapter",
]
