from __future__ import annotations

import logging
from typing import Any

import requests

from merism.recruitment.adapters.base import IMChannelBase, IMMessage, SendResult

logger = logging.getLogger(__name__)


class WecomBotAdapter(IMChannelBase):
    """Send-only WeCom Bot webhook adapter.

    Extracted from CowAgent channel/wecom_bot/ — retains only the webhook
    POST logic, with no dependency on CowAgent's config, bridge, or memory
    modules.

    WeCom Bot webhooks target a group chat; there is no per-user addressing.
    The webhook URL itself is the credential — no token management is needed.
    """

    channel_type: str = "wecom_bot"

    def __init__(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url

    # ------------------------------------------------------------------
    # Message building helpers
    # ------------------------------------------------------------------

    def _build_payload(self, message: IMMessage) -> dict[str, Any]:
        """Construct the WeCom Bot webhook request body from an IMMessage."""
        if message.msg_type == "markdown":
            return {"msgtype": "markdown", "markdown": {"content": message.content}}
        # Default to text for all other types (including "text" and unknown)
        return {"msgtype": "text", "text": {"content": message.content}}

    def _post(self, payload: dict[str, Any]) -> SendResult:
        """POST payload to the webhook URL and parse the WeCom response."""
        try:
            response = requests.post(self._webhook_url, json=payload, timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
            return SendResult(success=False, error=str(exc))

        data: dict[str, Any] = response.json()
        errcode: int = data.get("errcode", -1)
        if errcode != 0:
            errmsg: str = data.get("errmsg", "unknown error")
            return SendResult(success=False, error=errmsg, raw_response=data)

        return SendResult(success=True, raw_response=data)

    # ------------------------------------------------------------------
    # IMChannelBase interface
    # ------------------------------------------------------------------

    def send_message(self, recipient_id: str, message: IMMessage) -> SendResult:
        """Send a message via the webhook.

        WeCom Bot webhooks target a group chat, not individual users.
        The recipient_id is logged for traceability but does not affect routing.
        """
        logger.info(
            "WecomBotAdapter.send_message: recipient_id=%r is informational only "
            "(webhook sends to the configured group, not a specific user)",
            recipient_id,
        )
        return self._post(self._build_payload(message))

    def send_to_group(self, group_id: str, message: IMMessage) -> SendResult:
        """Send a message to the webhook group.

        The group_id parameter is accepted for interface compatibility but the
        destination is always the webhook URL configured at construction time.
        """
        return self._post(self._build_payload(message))

    def health_check(self) -> tuple[bool, str]:
        """Verify the webhook is reachable by sending a minimal ping message.

        Returns (True, "") on success or (False, error_message) on failure.
        """
        ping_payload: dict[str, Any] = {"msgtype": "text", "text": {"content": "ping"}}
        result = self._post(ping_payload)
        if result.success:
            return True, ""
        return False, result.error or "health check failed"

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> WecomBotAdapter:
        """Instantiate from a credential dict with key 'webhook_url'."""
        return cls(webhook_url=config["webhook_url"])
