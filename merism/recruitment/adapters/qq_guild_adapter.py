"""QQ 频道机器人适配器（QQ Guild Bot）。

使用腾讯官方 QQ 开放平台 API（https://bot.q.qq.com/wiki）：
- 鉴权：appid + token，通过 Authorization: Bot {appid}.{token} 头
- 发消息到频道子频道：POST /channels/{channel_id}/messages
- 发消息到频道私信（DM）：先创建私信会话，再发消息
- 健康检查：GET /users/@me 验证凭证有效性

凭证字段：
    appid   — QQ 开放平台应用 ID（数字字符串）
    token   — 机器人 Token（在 QQ 开放平台 → 开发设置 → 机器人 Token 获取）
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from merism.recruitment.adapters.base import IMChannelBase, IMMessage, SendResult

logger = logging.getLogger(__name__)

_QQ_GUILD_BASE_URL: str = "https://api.sgroup.qq.com"


class QQGuildAdapter(IMChannelBase):
    """Send-only QQ 频道机器人适配器。

    支持向子频道（channel）发消息，以及向频道成员发私信（DM）。
    凭证：appid + token，无需 OAuth，直接用 Bot 鉴权头。
    """

    channel_type: str = "qq_guild"

    def __init__(self, appid: str, token: str) -> None:
        self._appid = appid
        self._token = token

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _auth_header(self) -> dict[str, str]:
        return {
            "Authorization": f"Bot {self._appid}.{self._token}",
            "Content-Type": "application/json",
        }

    def _build_message_body(self, message: IMMessage) -> dict[str, Any]:
        """构造 QQ 频道消息请求体。

        QQ 频道消息支持 content（纯文本/Markdown）和 embed/ark 富文本。
        这里统一用 content 字段，Markdown 内容直接传入（频道支持部分 Markdown）。
        """
        body: dict[str, Any] = {"content": message.content}
        # 如果有 extra 字段（如 msg_id 用于被动回复），合并进去
        if message.extra:
            body.update(message.extra)
        return body

    # ------------------------------------------------------------------
    # IMChannelBase 接口
    # ------------------------------------------------------------------

    def send_message(self, recipient_id: str, message: IMMessage) -> SendResult:
        """向频道成员发私信（DM）。

        流程：先创建私信会话（POST /users/{user_id}/dms），再发消息。
        recipient_id 为频道成员的 user_id（非 QQ 号）。
        """
        # Step 1: 创建私信会话
        dm_url = f"{_QQ_GUILD_BASE_URL}/users/{recipient_id}/dms"
        try:
            dm_resp = requests.post(
                dm_url,
                headers=self._auth_header(),
                json={"recipient_id": recipient_id, "source_guild_id": ""},
                timeout=10,
            )
            dm_resp.raise_for_status()
        except requests.RequestException as exc:
            return SendResult(success=False, error=f"create DM session failed: {exc}")

        dm_data: dict[str, Any] = dm_resp.json()
        guild_id: str | None = dm_data.get("guild_id")
        if not guild_id:
            return SendResult(
                success=False,
                error="create DM session returned no guild_id",
                raw_response=dm_data,
            )

        # Step 2: 发私信消息
        msg_url = f"{_QQ_GUILD_BASE_URL}/dms/{guild_id}/messages"
        try:
            resp = requests.post(
                msg_url,
                headers=self._auth_header(),
                json=self._build_message_body(message),
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            return SendResult(success=False, error=str(exc))

        data: dict[str, Any] = resp.json()
        return SendResult(success=True, message_id=data.get("id"), raw_response=data)

    def send_to_group(self, group_id: str, message: IMMessage) -> SendResult:
        """向子频道（channel）发消息。

        group_id 为子频道 ID（channel_id），在 QQ 频道管理后台可查。
        """
        url = f"{_QQ_GUILD_BASE_URL}/channels/{group_id}/messages"
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
        return SendResult(success=True, message_id=data.get("id"), raw_response=data)

    def health_check(self) -> tuple[bool, str]:
        """通过 GET /users/@me 验证 appid + token 有效性。"""
        url = f"{_QQ_GUILD_BASE_URL}/users/@me"
        try:
            resp = requests.get(url, headers=self._auth_header(), timeout=10)
            resp.raise_for_status()
        except requests.RequestException as exc:
            return False, str(exc)

        data: dict[str, Any] = resp.json()
        # 正常返回包含 id 字段（机器人的 user_id）
        if not data.get("id"):
            return False, f"unexpected response: {data}"
        return True, ""

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> QQGuildAdapter:
        """从凭证 dict 实例化，需要 'appid' 和 'token' 两个字段。"""
        return cls(appid=config["appid"], token=config["token"])
