"""In-memory IM channel adapter fake.

Drop-in replacement for Merism's IM channel adapters (Feishu / WeCom / WeCom
Bot / QQ Group / QQ Guild). All variants share one in-memory implementation —
real channel-specific payload shaping is out of scope for tests.

Tests can assert:

- ``adapter.sent_messages`` — every message sent, in order
- ``adapter.health_check_calls`` — number of ``health_check()`` invocations
- ``adapter.force_next_failure(error="...")`` — simulate a channel error
- ``adapter.force_health_failure(error="...")`` — simulate an unhealthy channel
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ChannelType = Literal["feishu", "wecom", "wecom_bot", "qq_group", "qq_guild"]


@dataclass
class InMemorySentMessage:
    """A single recorded outbound message."""

    channel_type: ChannelType
    recipient_id: str
    content: str
    msg_type: str = "text"
    extra: dict[str, Any] = field(default_factory=dict)
    group_target: bool = False


@dataclass
class _SendResult:
    """Mirrors the shape of real adapters' ``SendResult`` without importing them."""

    success: bool
    message_id: str | None = None
    error: str | None = None


class InMemoryIMAdapter:
    """Fake IM adapter. Records every call; never hits the network.

    Example::

        adapter = InMemoryIMAdapter(channel_type="feishu")
        result = adapter.send_message("user_a", "hello")
        assert result.success
        assert adapter.sent_messages[0].recipient_id == "user_a"
    """

    def __init__(
        self,
        *,
        channel_type: ChannelType = "feishu",
        healthy: bool = True,
    ) -> None:
        self.channel_type: ChannelType = channel_type
        self._healthy = healthy
        self._health_error = "" if healthy else "channel marked unhealthy for tests"
        self._next_failure: str | None = None
        self.sent_messages: list[InMemorySentMessage] = []
        self.health_check_calls: int = 0

    # ─── Control surface (tests only) ────────────────────────────

    def reset(self) -> None:
        self.sent_messages.clear()
        self.health_check_calls = 0
        self._next_failure = None

    def force_next_failure(self, *, error: str = "forced failure") -> None:
        """The next ``send_*`` call will return failure."""
        self._next_failure = error

    def force_health_failure(self, *, error: str = "forced unhealthy") -> None:
        self._healthy = False
        self._health_error = error

    def restore_health(self) -> None:
        self._healthy = True
        self._health_error = ""

    # ─── Adapter protocol surface ───────────────────────────────

    def health_check(self) -> tuple[bool, str]:
        self.health_check_calls += 1
        return (self._healthy, self._health_error)

    def send_message(
        self,
        recipient_id: str,
        content_or_message: Any,
        *,
        msg_type: str = "text",
        **extra: Any,
    ) -> _SendResult:
        return self._record(
            recipient_id=recipient_id,
            content=_stringify(content_or_message),
            msg_type=msg_type,
            extra=extra,
            group_target=False,
        )

    def send_to_group(
        self,
        group_id: str,
        content_or_message: Any,
        *,
        msg_type: str = "text",
        **extra: Any,
    ) -> _SendResult:
        return self._record(
            recipient_id=group_id,
            content=_stringify(content_or_message),
            msg_type=msg_type,
            extra=extra,
            group_target=True,
        )

    # ─── Convenience query helpers for tests ────────────────────

    def messages_to(self, recipient_id: str) -> list[InMemorySentMessage]:
        return [m for m in self.sent_messages if m.recipient_id == recipient_id]

    @property
    def last_message(self) -> InMemorySentMessage:
        if not self.sent_messages:
            raise AssertionError("InMemoryIMAdapter has not sent any messages yet")
        return self.sent_messages[-1]

    # ─── Internals ──────────────────────────────────────────────

    def _record(
        self,
        *,
        recipient_id: str,
        content: str,
        msg_type: str,
        extra: dict[str, Any],
        group_target: bool,
    ) -> _SendResult:
        if self._next_failure is not None:
            error = self._next_failure
            self._next_failure = None
            return _SendResult(success=False, error=error)

        message = InMemorySentMessage(
            channel_type=self.channel_type,
            recipient_id=recipient_id,
            content=content,
            msg_type=msg_type,
            extra=extra,
            group_target=group_target,
        )
        self.sent_messages.append(message)
        return _SendResult(success=True, message_id=f"msg-{len(self.sent_messages)}")


def _stringify(value: Any) -> str:
    """Accept either a raw string or an ``IMMessage``-like object with ``content``."""
    if isinstance(value, str):
        return value
    content = getattr(value, "content", None)
    if isinstance(content, str):
        return content
    return str(value)
