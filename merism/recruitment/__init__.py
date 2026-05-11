"""Merism IM recruitment.

Implements the ``cowagent-im-recruitment`` spec:

- :mod:`merism.recruitment.adapters`           — Feishu / WeCom / QQ (group+guild) + WeCom Bot adapters
- :mod:`merism.recruitment.crypto`             — Fernet encrypt/decrypt for ``ChannelConfig.credentials_encrypted``
- :mod:`merism.recruitment.renderer`           — {{placeholder}} rendering + per-channel payload adaptation
- :mod:`merism.recruitment.rate_limit`         — per-channel 100msg/hour cap (Req 7.5)
- :mod:`merism.recruitment.builtin_templates`  — system-owned MessageTemplate seeds

Models live under :mod:`merism.models.recruitment`:
``ChannelConfig``, ``MessageTemplate``, ``RecruitmentBroadcast``,
``DeliveryRecord``, ``ChannelHealthCheck``.
"""

from __future__ import annotations

from merism.recruitment.adapters import (
    CHANNEL_FEISHU,
    CHANNEL_QQ_GROUP,
    CHANNEL_QQ_GUILD,
    CHANNEL_WECOM_BOT,
    SUPPORTED_CHANNEL_TYPES,
)
from merism.recruitment.adapters.base import IMChannelBase, IMMessage, SendResult
from merism.recruitment.adapters.factory import get_adapter
from merism.recruitment.crypto import decrypt_credentials, encrypt_credentials

__all__ = [
    # channel type constants
    "CHANNEL_FEISHU",
    "CHANNEL_WECOM_BOT",
    "CHANNEL_QQ_GROUP",
    "CHANNEL_QQ_GUILD",
    "SUPPORTED_CHANNEL_TYPES",
    # adapter protocol
    "IMChannelBase",
    "IMMessage",
    "SendResult",
    # factory
    "get_adapter",
    # crypto
    "encrypt_credentials",
    "decrypt_credentials",
]
