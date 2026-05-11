from __future__ import annotations

import json
import time
import threading
from typing import Any

import requests

from merism.recruitment.adapters.base import IMChannelBase, IMMessage, SendResult

# Feishu token validity is 2 hours; cache for slightly less to avoid edge-case expiry
_TOKEN_TTL_SECONDS: int = 7000  # ~1h 56m

# Module-level token cache: {app_id: (token, expiry_timestamp)}
_token_cache: dict[str, tuple[str, float]] = {}
_token_cache_lock: threading.Lock = threading.Lock()

_FEISHU_BASE_URL: str = "https://open.feishu.cn"
_AUTH_ENDPOINT: str = "/open-apis/auth/v3/tenant_access_token/internal"
_SEND_MESSAGE_ENDPOINT: str = "/open-apis/im/v1/messages"


class FeishuAdapter(IMChannelBase):
    """Send-only Feishu Open API adapter.

    Extracted from CowAgent channel/feishu/feishu_channel.py — retains only
    the tenant_access_token fetch and message send logic, with no dependency
    on CowAgent's config, bridge, or memory modules.
    """

    channel_type: str = "feishu"

    def __init__(self, app_id: str, app_secret: str) -> None:
        self._app_id = app_id
        self._app_secret = app_secret

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    def _get_token(self) -> str:
        """Return a valid tenant_access_token, fetching a fresh one if needed.

        Uses a module-level cache keyed by app_id so multiple adapter instances
        sharing the same credentials share a single token. Thread-safe via lock.
        """
        with _token_cache_lock:
            cached = _token_cache.get(self._app_id)
            if cached is not None:
                token, expiry = cached
                if time.monotonic() < expiry:
                    return token

            # Cache miss or expired — fetch a new token
            token = self._fetch_token()
            _token_cache[self._app_id] = (token, time.monotonic() + _TOKEN_TTL_SECONDS)
            return token

    def _fetch_token(self) -> str:
        """Call Feishu auth endpoint and return the tenant_access_token string."""
        url = f"{_FEISHU_BASE_URL}{_AUTH_ENDPOINT}"
        payload = {"app_id": self._app_id, "app_secret": self._app_secret}
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        token: str = data["tenant_access_token"]
        return token

    # ------------------------------------------------------------------
    # Message building helpers
    # ------------------------------------------------------------------

    def _build_message_body(self, receive_id: str, message: IMMessage) -> dict[str, Any]:
        """Construct the Feishu message request body from an IMMessage."""
        if message.msg_type == "text":
            msg_type = "text"
            content = json.dumps({"text": message.content})
        elif message.msg_type in ("markdown", "post"):
            # Feishu "post" (rich text) is the closest equivalent to Markdown
            msg_type = "post"
            content = json.dumps(
                {
                    "post": {
                        "zh_cn": {
                            "title": "",
                            "content": [[{"tag": "text", "text": message.content}]],
                        }
                    }
                }
            )
        else:
            # Fallback: treat unknown types as plain text
            msg_type = "text"
            content = json.dumps({"text": message.content})

        body: dict[str, Any] = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": content,
        }
        return body

    def _send(self, receive_id: str, receive_id_type: str, message: IMMessage) -> SendResult:
        """Internal send helper shared by send_message and send_to_group."""
        try:
            token = self._get_token()
        except requests.RequestException as exc:
            return SendResult(success=False, error=f"token fetch failed: {exc}")

        url = f"{_FEISHU_BASE_URL}{_SEND_MESSAGE_ENDPOINT}"
        params = {"receive_id_type": receive_id_type}
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        body = self._build_message_body(receive_id, message)

        try:
            response = requests.post(url, params=params, headers=headers, json=body, timeout=15)
            response.raise_for_status()
        except requests.RequestException as exc:
            return SendResult(success=False, error=str(exc))

        data: dict[str, Any] = response.json()
        # Feishu wraps results in data.data; message_id lives there
        inner: dict[str, Any] = data.get("data", {})
        message_id: str | None = inner.get("message_id")
        return SendResult(success=True, message_id=message_id, raw_response=data)

    # ------------------------------------------------------------------
    # IMChannelBase interface
    # ------------------------------------------------------------------

    def send_message(self, recipient_id: str, message: IMMessage) -> SendResult:
        """Send a message to an individual user identified by open_id."""
        return self._send(recipient_id, "open_id", message)

    def send_to_group(self, group_id: str, message: IMMessage) -> SendResult:
        """Send a message to a group chat identified by chat_id."""
        return self._send(group_id, "chat_id", message)

    def health_check(self) -> tuple[bool, str]:
        """Verify credentials by attempting a token fetch.

        Returns (True, "") on success or (False, error_message) on failure.
        """
        try:
            self._fetch_token()
            return True, ""
        except requests.RequestException as exc:
            return False, str(exc)
        except KeyError as exc:
            return False, f"unexpected auth response shape: {exc}"

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> FeishuAdapter:
        """Instantiate from a credential dict with keys 'app_id' and 'app_secret'."""
        return cls(app_id=config["app_id"], app_secret=config["app_secret"])
