"""QQ 群机器人适配器（QQ Group Bot）。

使用腾讯 2024 年开放的 QQ 群 Bot API（https://bot.q.qq.com/wiki/develop/api-v2/）：
- 鉴权：appid + client_secret，通过 OAuth2 client_credentials 获取 access_token
- 发消息到 QQ 群：POST /v2/groups/{group_openid}/messages
- 发消息到 QQ 用户（单聊）：POST /v2/users/{openid}/messages
- 健康检查：通过 token 获取验证凭证有效性

凭证字段：
    appid          — QQ 开放平台应用 ID
    client_secret  — 应用密钥（在 QQ 开放平台 → 开发设置获取）

注意：QQ 群 Bot 目前仅支持被动回复（需要 event_id 或 msg_id）和主动推送（需申请权限）。
本适配器使用主动推送模式，需要在 QQ 开放平台申请"主动推送"权限。
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import requests

from merism.recruitment.adapters.base import IMChannelBase, IMMessage, SendResult

logger = logging.getLogger(__name__)

_QQ_GROUP_BASE_URL: str = "https://api.sgroup.qq.com"
_QQ_AUTH_URL: str = "https://bots.qq.com/app/getAppAccessToken"
_TOKEN_TTL_BUFFER_SECONDS: int = 60  # 提前 60s 刷新

# 模块级 token 缓存：{appid: (access_token, expiry_timestamp)}
_token_cache: dict[str, tuple[str, float]] = {}
_token_cache_lock: threading.Lock = threading.Lock()


class QQGroupAdapter(IMChannelBase):
    """Send-only QQ 群机器人适配器。

    支持向 QQ 群（group_openid）和 QQ 用户（openid）发消息。
    使用 OAuth2 client_credentials 鉴权，access_token 自动缓存刷新。
    """

    channel_type: str = "qq_group"

    def __init__(self, appid: str, client_secret: str) -> None:
        self._appid = appid
        self._client_secret = client_secret

    # ------------------------------------------------------------------
    # Token 管理
    # ------------------------------------------------------------------

    def _get_access_token(self) -> str:
        """获取有效的 access_token，过期自动刷新，线程安全。"""
        with _token_cache_lock:
            cached = _token_cache.get(self._appid)
            if cached is not None:
                token, expiry = cached
                if time.monotonic() < expiry:
                    return token
            token, expires_in = self._fetch_access_token()
            expiry = time.monotonic() + expires_in - _TOKEN_TTL_BUFFER_SECONDS
            _token_cache[self._appid] = (token, expiry)
            return token

    def _fetch_access_token(self) -> tuple[str, int]:
        """调用 QQ 开放平台获取 access_token，返回 (token, expires_in_seconds)。"""
        payload = {
            "appId": self._appid,
            "clientSecret": self._client_secret,
        }
        try:
            resp = requests.post(_QQ_AUTH_URL, json=payload, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"QQ Group Bot token fetch failed: {exc}") from exc

        data: dict[str, Any] = resp.json()
        token: str = data.get("access_token", "")
        expires_in: int = int(data.get("expires_in", 7200))
        if not token:
            raise RuntimeError(f"QQ Group Bot token fetch returned no access_token: {data}")
        return token, expires_in

    def _auth_header(self) -> dict[str, str]:
        token = self._get_access_token()
        return {
            "Authorization": f"QQBot {token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # 消息体构造
    # ------------------------------------------------------------------

    def _build_message_body(self, message: IMMessage) -> dict[str, Any]:
        """构造 QQ 群/单聊消息请求体。

        QQ 群 Bot API v2 消息体：
        - msg_type=0: 文本消息（content 字段）
        - msg_type=2: Markdown 消息（markdown.content 字段）
        """
        if message.msg_type == "markdown":
            body: dict[str, Any] = {
                "msg_type": 2,
                "markdown": {"content": message.content},
            }
        else:
            body = {
                "msg_type": 0,
                "content": message.content,
            }
        # 合并 extra（如 msg_seq 防重放、event_id 被动回复等）
        if message.extra:
            body.update(message.extra)
        return body

    def _post_message(self, url: str, message: IMMessage) -> SendResult:
        """通用发消息方法。"""
        try:
            resp = requests.post(
                url,
                headers=self._auth_header(),
                json=self._build_message_body(message),
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            return SendResult(success=False, error=str(exc))

        data: dict[str, Any] = resp.json()
        # QQ API 错误通过 code 字段返回（0 或无 code = 成功）
        code: int = data.get("code", 0)
        if code != 0:
            return SendResult(
                success=False,
                error=data.get("message", f"QQ API error code {code}"),
                raw_response=data,
            )
        return SendResult(success=True, message_id=data.get("id"), raw_response=data)

    # ------------------------------------------------------------------
    # IMChannelBase 接口
    # ------------------------------------------------------------------

    def send_message(self, recipient_id: str, message: IMMessage) -> SendResult:
        """向 QQ 用户发单聊消息。

        recipient_id 为用户的 openid（非 QQ 号，由 QQ 开放平台分配）。
        """
        url = f"{_QQ_GROUP_BASE_URL}/v2/users/{recipient_id}/messages"
        return self._post_message(url, message)

    def send_to_group(self, group_id: str, message: IMMessage) -> SendResult:
        """向 QQ 群发消息。

        group_id 为群的 group_openid（由 QQ 开放平台分配，非普通群号）。
        """
        url = f"{_QQ_GROUP_BASE_URL}/v2/groups/{group_id}/messages"
        return self._post_message(url, message)

    def health_check(self) -> tuple[bool, str]:
        """通过获取 access_token 验证 appid + client_secret 有效性。"""
        try:
            self._fetch_access_token()
            return True, ""
        except RuntimeError as exc:
            return False, str(exc)
        except Exception as exc:
            return False, f"health check failed: {exc}"

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> QQGroupAdapter:
        """从凭证 dict 实例化，需要 'appid' 和 'client_secret' 两个字段。"""
        return cls(appid=config["appid"], client_secret=config["client_secret"])
