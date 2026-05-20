# Technical Design: CowAgent IM 渠道招募集成

## Architecture Overview

将 CowAgent 的 Channel 发送能力以 vendored adapter 形式集成到 Merism，不引入 CowAgent 的 Agent/Bridge/Memory 等模块，仅提取 **send-only** 的渠道抽象。

```
┌─────────────────────────────────────────────────────┐
│  Merism Django App (products/studies)                │
│                                                     │
│  ┌──────────┐   ┌──────────────┐   ┌────────────┐  │
│  │ REST API │──▶│ Celery Tasks │──▶│  Adapters  │  │
│  └──────────┘   └──────────────┘   └─────┬──────┘  │
│                                           │         │
│  ┌──────────────────────────────────────┐ │         │
│  │  Django Models (ChannelConfig,       │ │         │
│  │  MessageTemplate, Broadcast,         │ │         │
│  │  DeliveryRecord)                     │ │         │
│  └──────────────────────────────────────┘ │         │
└───────────────────────────────────────────┼─────────┘
                                            │
                    ┌───────────────────────────────┐
                    │  Vendored Channel Adapters     │
                    │  (from CowAgent, send-only)   │
                    │                               │
                    │  ├── base.py (IMChannelBase)   │
                    │  ├── feishu_adapter.py         │
                    │  └── wecom_bot_adapter.py      │
                    └───────────────┬───────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │  IM Platform APIs              │
                    │  (Feishu Open API / WeCom)     │
                    └───────────────────────────────┘
```

## Component Design

### 1. Vendored Channel Adapters

Location: `products/studies/backend/recruitment/channels/`

从 CowAgent 提取最小化的发送逻辑，不依赖 CowAgent 的 config.py、bridge、common 等模块。

#### base.py - IMChannelBase

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass
class IMMessage:
    """Platform-agnostic outbound message."""
    content: str           # 消息正文（纯文本或 Markdown）
    msg_type: str = "text" # text | markdown | interactive (feishu card)
    extra: dict[str, Any] | None = None  # 平台特定字段

@dataclass
class SendResult:
    success: bool
    message_id: str | None = None
    error: str | None = None
    raw_response: dict[str, Any] | None = None

class IMChannelBase:
    """Send-only channel adapter base class (adapted from CowAgent Channel)."""
    channel_type: str = ""

    def send_message(self, recipient_id: str, message: IMMessage) -> SendResult:
        raise NotImplementedError

    def send_to_group(self, group_id: str, message: IMMessage) -> SendResult:
        raise NotImplementedError

    def health_check(self) -> tuple[bool, str]:
        """Returns (healthy, error_message)."""
        raise NotImplementedError

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "IMChannelBase":
        raise NotImplementedError
```

#### feishu_adapter.py

从 CowAgent `channel/feishu/feishu_channel.py` 提取发送逻辑，使用 `requests` 直接调用飞书 Open API：
- `POST /open-apis/auth/v3/tenant_access_token/internal` → 获取 tenant_access_token
- `POST /open-apis/im/v1/messages` → 发送消息到用户/群组
- Token 缓存 2 小时（飞书 token 有效期 2h）

#### wecom_bot_adapter.py

从 CowAgent `channel/wecom_bot/` 提取 Webhook 发送逻辑：
- `POST {webhook_url}` → 直接发送 Markdown/Text 消息
- 无需 token 管理，Webhook URL 本身即凭证

### 2. Django Models

Location: `products/studies/backend/models.py` (或拆分到 `recruitment/models.py`)

```python
class ChannelConfig(models.Model):
    """IM 渠道配置，按 Team 隔离。"""
    class ChannelType(models.TextChoices):
        FEISHU = "feishu", "飞书"
        WECOM_BOT = "wecom_bot", "企微机器人"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        ERROR = "error", "Error"

    id = models.UUIDField(primary_key=True, default=uuid4)
    team = models.ForeignKey("merism.Team", on_delete=models.CASCADE)
    channel_type = models.CharField(max_length=20, choices=ChannelType.choices)
    name = models.CharField(max_length=100)  # 用户自定义名称
    # 加密存储的凭证 JSON (Fernet)
    credentials_encrypted = models.BinaryField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INACTIVE)
    last_health_check_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "merism_channel_config"


class MessageTemplate(models.Model):
    """招募消息模板。"""
    id = models.UUIDField(primary_key=True, default=uuid4)
    team = models.ForeignKey("merism.Team", on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    content = models.TextField()  # 支持 {{variable}} 占位符
    msg_format = models.CharField(max_length=20, default="markdown")  # text | markdown
    is_builtin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "merism_message_template"


class RecruitmentBroadcast(models.Model):
    """一次招募广播任务。"""
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENDING = "sending", "Sending"
        COMPLETED = "completed", "Completed"
        PARTIALLY_FAILED = "partially_failed", "Partially Failed"

    id = models.UUIDField(primary_key=True, default=uuid4)
    team = models.ForeignKey("merism.Team", on_delete=models.CASCADE)
    study = models.ForeignKey("studies.Study", on_delete=models.CASCADE)
    channel_config = models.ForeignKey(ChannelConfig, on_delete=models.PROTECT)
    template = models.ForeignKey(MessageTemplate, on_delete=models.SET_NULL, null=True)
    rendered_content = models.TextField()  # 最终渲染后的消息内容
    recipients = models.JSONField(default=list)  # ["group_id_1", "user_id_2", ...]
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    total_count = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "merism_recruitment_broadcast"


class DeliveryRecord(models.Model):
    """单条消息投递记录。"""
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid4)
    broadcast = models.ForeignKey(RecruitmentBroadcast, on_delete=models.CASCADE, related_name="deliveries")
    recipient_id = models.CharField(max_length=200)  # group_id or user_id
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    platform_message_id = models.CharField(max_length=200, blank=True, default="")
    error_detail = models.TextField(blank=True, default="")
    retry_count = models.IntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "merism_delivery_record"
```

### 3. Celery Tasks

Location: `products/studies/backend/recruitment/tasks.py`

```python
@shared_task(ignore_result=True, bind=True, max_retries=3)
def dispatch_recruitment_delivery(self, broadcast_id: str) -> None:
    """逐条发送广播中的消息，更新 DeliveryRecord 状态。"""
    # 1. 加载 broadcast + channel_config
    # 2. 解密凭证，实例化 adapter
    # 3. 遍历 recipients，逐条发送
    # 4. 更新 DeliveryRecord 状态
    # 5. 更新 broadcast 汇总计数
    # 6. 单条失败不中断，记录错误继续

@shared_task(ignore_result=True)
def sync_cowagent_channel_mirror() -> None:
    """Celery beat 定期健康检查所有 active 渠道。"""
    # 1. 查询所有 status=active 的 ChannelConfig
    # 2. 对每个调用 adapter.health_check()
    # 3. 失败则更新 status=error + last_error
    # 4. 之前 error 现在通过则恢复 status=active

@shared_task(ignore_result=True)
def retry_failed_deliveries(broadcast_id: str) -> None:
    """重试某次广播中所有 failed 的投递记录。"""
```

### 4. REST API

Location: `products/studies/backend/recruitment/api.py`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/studies/channels/` | GET/POST | 列出/创建渠道配置 |
| `/api/studies/channels/{id}/` | GET/PUT/DELETE | 单个渠道 CRUD |
| `/api/studies/channels/{id}/test/` | POST | 发送测试消息 |
| `/api/studies/templates/` | GET/POST | 列出/创建消息模板 |
| `/api/studies/templates/{id}/` | GET/PUT/DELETE | 单个模板 CRUD |
| `/api/studies/templates/{id}/preview/` | POST | 渲染模板预览 |
| `/api/studies/broadcasts/` | GET/POST | 列出/创建广播 |
| `/api/studies/broadcasts/{id}/` | GET | 广播详情（含投递统计） |
| `/api/studies/broadcasts/{id}/retry/` | POST | 重试失败投递 |

### 5. Credential Encryption

使用 Django Fernet（`cryptography` 库）：
- 加密 key 从 `SECRET_KEY` 派生
- `credentials_encrypted` 存储 Fernet 加密后的 JSON bytes
- 解密仅在 Celery task 执行时进行，API 层不返回明文

### 6. Rate Limiting

- 使用 Django cache (Redis) 实现滑动窗口计数器
- Key: `merism:channel_rate:{channel_config_id}`
- 限制: 100 messages/hour/channel
- 超限时消息进入延迟队列，下一窗口自动发送

### 7. Frontend Components (概要)

- `ChannelConfigWizard` - 引导式配置向导（3 步）
- `TemplateEditor` - 模板编辑器 + 实时预览
- `BroadcastComposer` - 广播创建页（选渠道 → 选模板 → 填收件人 → 发送）
- `DeliveryStatusPanel` - 投递状态面板

## Dependencies

- `requests` (已有) - HTTP 调用飞书/企微 API
- `cryptography` (已有) - Fernet 加密
- 无需安装 CowAgent 整体依赖，仅 vendor 其发送逻辑

## Migration Plan

1. 添加 4 个 Django model → `makemigrations`
2. 创建 3 个内置模板 (data migration)
3. 注册 Celery beat schedule for `sync_cowagent_channel_mirror`
4. Feature flag: `MERISM_IM_RECRUITMENT` 控制功能可见性
