"""Template rendering engine for IM recruitment messages.

Renders MessageTemplate content by substituting {{variable}} placeholders
with context values, validates required placeholders are present, and adapts
the rendered Markdown to platform-specific formats:

  - feishu: Markdown → Feishu interactive card JSON (msg_type=interactive)
  - wecom_bot: Markdown → WeCom Markdown message payload

Refs: Requirement 2 (AC 2-6), Design §1.
"""

from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Placeholder helpers
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")

REQUIRED_PLACEHOLDERS: frozenset[str] = frozenset({"study_name", "study_link"})
SUPPORTED_PLACEHOLDERS: frozenset[str] = frozenset(
    {"study_name", "study_link", "deadline", "reward", "researcher_name"}
)


def extract_placeholders(content: str) -> set[str]:
    """Return the set of variable names referenced in *content*."""
    return {m.group(1) for m in _PLACEHOLDER_RE.finditer(content)}


def validate_required_placeholders(content: str) -> list[str]:
    """Return a list of missing required placeholder names (empty = valid)."""
    present = extract_placeholders(content)
    return sorted(REQUIRED_PLACEHOLDERS - present)


# ---------------------------------------------------------------------------
# Core render
# ---------------------------------------------------------------------------


def render_template(content: str, context: dict[str, Any]) -> tuple[str, list[str]]:
    """Render *content* by substituting {{variable}} placeholders.

    Returns:
        (rendered_text, missing_variables)

    - Variables present in *context* are substituted.
    - Variables absent from *context* are left as ``{{variable}}`` tokens so
      the caller can surface them to the user (Requirement 2 AC 6).
    - ``missing_variables`` lists the names of placeholders that were not
      supplied in *context* (empty list when all are provided).
    """
    rendered = content
    for key, value in context.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value))

    # Collect any remaining unresolved placeholders
    missing = sorted(extract_placeholders(rendered))
    return rendered, missing


# ---------------------------------------------------------------------------
# Format adaptation
# ---------------------------------------------------------------------------


def _markdown_to_feishu_card(markdown_text: str, title: str = "招募邀请") -> dict[str, Any]:
    """Convert a Markdown string to a Feishu interactive card JSON payload.

    The card uses a single ``div`` element with ``lark_md`` content so that
    Markdown formatting (bold, links, line breaks) is preserved inside Feishu.

    Refs: Feishu Open API — Interactive Card schema.
    """
    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": markdown_text,
                    },
                }
            ],
        },
    }


def _markdown_to_wecom_payload(markdown_text: str) -> dict[str, Any]:
    """Wrap a Markdown string in a WeCom bot webhook message payload.

    WeCom bot webhooks accept ``msgtype=markdown`` with a ``content`` field
    that supports a subset of Markdown (bold, links, line breaks via ``<br>``).

    Refs: WeCom Bot Webhook API.
    """
    return {
        "msgtype": "markdown",
        "markdown": {
            "content": markdown_text,
        },
    }


def adapt_for_channel(
    rendered_text: str,
    channel_type: str,
    msg_format: str = "markdown",
    title: str = "招募邀请",
) -> dict[str, Any]:
    """Adapt rendered text to the wire format expected by *channel_type*.

    Args:
        rendered_text: The fully-rendered message body (Markdown or plain text).
        channel_type: ``"feishu"`` or ``"wecom_bot"``.
        msg_format: ``"markdown"`` (default) or ``"text"``.
        title: Card title used only for Feishu interactive cards.

    Returns:
        A dict that can be passed directly to the channel adapter's
        ``send_message`` / ``send_to_group`` as the ``extra`` payload, or
        used to construct an ``IMMessage``.

    Raises:
        ValueError: If *channel_type* is not recognised.
    """
    if channel_type == "feishu":
        if msg_format == "markdown":
            return _markdown_to_feishu_card(rendered_text, title=title)
        # Plain text → simple feishu text message
        return {"msg_type": "text", "content": {"text": rendered_text}}

    if channel_type == "wecom_bot":
        if msg_format == "markdown":
            return _markdown_to_wecom_payload(rendered_text)
        # Plain text → wecom text message
        return {"msgtype": "text", "text": {"content": rendered_text}}

    if channel_type == "qq_guild":
        # QQ 频道支持部分 Markdown，msg_type=2 为 Markdown，0 为纯文本
        if msg_format == "markdown":
            return {"msg_type": 2, "content": rendered_text}
        return {"msg_type": 0, "content": rendered_text}

    if channel_type == "qq_group":
        # QQ 群 Bot API v2：msg_type=2 Markdown，msg_type=0 纯文本
        if msg_format == "markdown":
            return {"msg_type": 2, "markdown": {"content": rendered_text}}
        return {"msg_type": 0, "content": rendered_text}

    raise ValueError(f"Unsupported channel_type: {channel_type!r}")

# ---------------------------------------------------------------------------
# High-level convenience
# ---------------------------------------------------------------------------


def render_and_adapt(
    content: str,
    context: dict[str, Any],
    channel_type: str,
    msg_format: str = "markdown",
    title: str = "招募邀请",
) -> tuple[dict[str, Any], list[str]]:
    """Render *content* with *context* and adapt the result for *channel_type*.

    Returns:
        (adapted_payload, missing_variables)

    This is the primary entry point used by Celery tasks when constructing
    the final message payload before calling the channel adapter.
    """
    rendered, missing = render_template(content, context)
    payload = adapt_for_channel(rendered, channel_type, msg_format=msg_format, title=title)
    return payload, missing
