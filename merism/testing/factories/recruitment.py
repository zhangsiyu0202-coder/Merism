"""Recruitment-domain factories.

ChannelConfig (per-team IM channel credentials), MessageTemplate (admin-crafted
invite text), RecruitmentBroadcast (a batch send), DeliveryRecord (per-recipient
outcome).

Credentials are deliberately left as plain dicts — we do NOT encrypt in stub
mode because the Fernet roundtrip is exercised in its own dedicated test.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any, Literal


ChannelType = Literal["feishu", "wecom", "wecom_bot", "qq_group", "qq_guild"]


def make_channel_config(
    *,
    channel_type: ChannelType = "feishu",
    name: str | None = None,
    status: str = "active",
    credentials: dict[str, Any] | None = None,
    team_id: int = 1,
    adapter: Any | None = None,
    stub: bool = True,
    **extra: Any,
) -> SimpleNamespace:
    """Build a ChannelConfig.

    If ``adapter`` is provided (typically an ``InMemoryIMAdapter``), it is
    attached to ``channel.adapter`` for convenient access in tests.
    """
    if not stub:
        raise NotImplementedError("make_channel_config(stub=False) requires Phase C1")

    default_creds: dict[str, Any] = {
        "feishu": {"app_id": "fs-app", "app_secret": "fs-secret"},
        "wecom": {"corp_id": "wc-corp", "agent_id": "wc-agent", "secret": "wc-secret"},
        "wecom_bot": {"webhook_url": "https://wcbot.test/abc"},
        "qq_group": {"appid": "qqg-appid", "client_secret": "qqg-secret"},
        "qq_guild": {"appid": "qqguild-appid", "token": "qqguild-token"},
    }

    resolved_name = name or f"{channel_type}-channel-{uuid.uuid4().hex[:6]}"
    return SimpleNamespace(
        id=uuid.uuid4(),
        pk=uuid.uuid4(),
        channel_type=channel_type,
        name=resolved_name,
        status=status,
        credentials=credentials if credentials is not None else default_creds[channel_type],
        team_id=team_id,
        adapter=adapter,
        consecutive_failures=0,
        last_healthy_at=None,
        **extra,
    )


def make_message_template(
    *,
    name: str = "Recruitment invite",
    content: str = "Hi {{name}}, please join {{study_link}} for {{study_name}}.",
    channel_type: ChannelType = "feishu",
    is_system: bool = False,
    team_id: int = 1,
    stub: bool = True,
) -> SimpleNamespace:
    """Build a MessageTemplate."""
    if not stub:
        raise NotImplementedError("make_message_template(stub=False) requires Phase C1")
    return SimpleNamespace(
        id=uuid.uuid4(),
        pk=uuid.uuid4(),
        name=name,
        content=content,
        channel_type=channel_type,
        is_system=is_system,
        team_id=team_id,
    )


def make_broadcast(
    *,
    study: SimpleNamespace | None = None,
    channel: SimpleNamespace | None = None,
    template: SimpleNamespace | None = None,
    status: str = "draft",
    recipients: list[str] | None = None,
    retry_count: int = 0,
    team_id: int = 1,
    stub: bool = True,
    **extra: Any,
) -> SimpleNamespace:
    """Build a RecruitmentBroadcast. ``recipients`` is a list of recipient IDs.

    If ``study`` / ``channel`` / ``template`` are omitted, minimal stubs are
    created so tests can focus on broadcast logic.
    """
    if not stub:
        raise NotImplementedError("make_broadcast(stub=False) requires Phase C1")

    if study is None:
        from merism.testing.factories.study import make_study

        study = make_study(team_id=team_id, stub=True)
    if channel is None:
        channel = make_channel_config(team_id=team_id, stub=True)
    if template is None:
        template = make_message_template(team_id=team_id, stub=True)

    recipients = list(recipients or [])
    broadcast_id = uuid.uuid4()
    return SimpleNamespace(
        id=broadcast_id,
        pk=broadcast_id,
        study=study,
        study_id=study.id,
        channel=channel,
        channel_id=channel.id,
        template=template,
        template_id=template.id,
        status=status,
        retry_count=retry_count,
        team_id=team_id,
        recipients=recipients,
        total_count=len(recipients),
        sent_count=0,
        failed_count=0,
        deliveries=[],
        **extra,
    )


def make_delivery(
    broadcast: SimpleNamespace,
    *,
    recipient_id: str,
    status: str = "pending",
    error: str | None = None,
    message_id: str | None = None,
    stub: bool = True,
) -> SimpleNamespace:
    """Build a DeliveryRecord attached to a broadcast."""
    if not stub:
        raise NotImplementedError("make_delivery(stub=False) requires Phase C1")
    delivery = SimpleNamespace(
        id=uuid.uuid4(),
        pk=uuid.uuid4(),
        broadcast=broadcast,
        broadcast_id=broadcast.id,
        recipient_id=recipient_id,
        status=status,
        error=error,
        message_id=message_id,
        team_id=broadcast.team_id,
    )
    broadcast.deliveries.append(delivery)
    return delivery
