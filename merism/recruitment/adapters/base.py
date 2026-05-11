from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class IMMessage:
    """Platform-agnostic outbound message."""

    content: str  # 消息正文（纯文本或 Markdown）
    msg_type: str = "text"  # text | markdown | interactive (feishu card)
    extra: dict[str, Any] | None = None  # 平台特定字段


@dataclass
class SendResult:
    success: bool
    message_id: str | None = None
    error: str | None = None
    raw_response: dict[str, Any] | None = None


class IMChannelBase:
    """Send-only channel adapter base class (adapted from CowAgent Channel).

    Subclasses implement the four abstract methods for each IM platform.
    The base class deliberately raises NotImplementedError rather than using
    abc.ABC so that partial adapters (e.g. group-only channels) can override
    only the methods they support without triggering ABC instantiation errors.
    """

    channel_type: str = ""

    def send_message(self, recipient_id: str, message: IMMessage) -> SendResult:
        raise NotImplementedError

    def send_to_group(self, group_id: str, message: IMMessage) -> SendResult:
        raise NotImplementedError

    def health_check(self) -> tuple[bool, str]:
        """Returns (healthy, error_message)."""
        raise NotImplementedError

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> IMChannelBase:
        raise NotImplementedError
