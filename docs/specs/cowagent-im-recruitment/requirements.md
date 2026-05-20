# Requirements Document

## Introduction

将 CowAgent 的 Channel 层（IM 渠道抽象）直接集成到 Merism 项目中，使研究团队能够通过飞书、企微机器人等即时通讯渠道向目标用户群发送研究招募消息和参与链接。

核心目标：**使用层面的新手友好**——非技术背景的研究人员也能在几分钟内完成渠道配置并发出第一条招募消息，无需理解底层 API 或编写代码。

集成方式为 vendored/adapted module（非独立服务），复用 CowAgent 的 Channel 基类和飞书/企微实现，适配为 Django model + Celery task 驱动的内部模块。

## Glossary

- **Recruitment_Broadcast**: 一次招募广播任务，包含目标渠道、消息模板、研究链接，由 Celery task 异步执行
- **IM_Channel**: 即时通讯渠道实例（如一个飞书机器人、一个企微 Webhook），对应 CowAgent Channel 基类的适配实现
- **Channel_Config**: 存储在数据库中的渠道凭证和配置（app_id、secret、webhook_url 等），按 Team 隔离
- **Message_Template**: 预定义的招募消息模板，支持变量插值（研究名称、链接、截止日期等）
- **Delivery_Record**: 单条消息的投递记录，追踪发送状态（pending/sent/failed/delivered）
- **Channel_Adapter**: 从 CowAgent Channel 基类适配而来的 Merism 内部发送器，负责调用 IM 平台 API
- **Study**: Merism 中的研究实体，招募广播关联到具体 Study
- **StudyLink**: 研究参与链接，嵌入招募消息中供受邀者点击参与
- **Team**: `merism.Team`(merism-app 中的团队实体)，所有渠道配置按 Team 隔离
- **Config_Wizard**: 引导式配置向导 UI，帮助用户逐步完成渠道接入

## Requirements

### Requirement 1: IM 渠道配置管理

**User Story:** As a 研究团队管理员, I want 通过可视化界面配置 IM 渠道（飞书/企微机器人）的接入凭证, so that 团队成员可以使用这些渠道发送招募消息而无需了解 API 细节。

#### Acceptance Criteria

1. THE Channel_Config SHALL store channel credentials (app_id, app_secret, webhook_url, token) encrypted at rest, scoped to a Team.
2. WHEN a user opens the channel configuration page, THE Config_Wizard SHALL display a step-by-step guide with platform-specific screenshots showing where to obtain each credential.
3. WHEN a user submits channel credentials, THE Channel_Config SHALL validate connectivity by sending a test message to a designated test target before saving.
4. IF the connectivity test fails, THEN THE Config_Wizard SHALL display the specific error reason (e.g., "Invalid app_secret" or "Webhook URL unreachable") and suggest corrective actions.
5. WHEN a channel configuration is saved successfully, THE System SHALL mark the channel status as "active" and display a green indicator in the channel list.
6. THE Channel_Config SHALL support at minimum two channel types: feishu (飞书) and wecom_bot (企微机器人).
7. WHILE a channel status is "inactive" or "error", THE System SHALL prevent that channel from being selected as a broadcast target.

### Requirement 2: 招募消息模板

**User Story:** As a 研究人员, I want 使用预定义的消息模板来编写招募消息, so that 我可以快速创建专业的招募内容而不必从零开始撰写。

#### Acceptance Criteria

1. THE Message_Template SHALL provide at least three built-in templates: "简洁邀请"、"详细说明"、"紧急招募".
2. THE Message_Template SHALL support variable placeholders: {{study_name}}, {{study_link}}, {{deadline}}, {{reward}}, {{researcher_name}}.
3. WHEN a user selects a template, THE System SHALL render a real-time preview with the current Study context values filled in.
4. WHEN a user edits a template, THE System SHALL validate that all required placeholders ({{study_name}} and {{study_link}}) are present before allowing save.
5. THE Message_Template SHALL support both plain text and rich text (Markdown) formats, adapting output to each channel's capability (feishu supports rich cards; wecom_bot supports Markdown).
6. WHEN a template references a variable that has no value in the current context, THE System SHALL highlight the missing variable and prompt the user to provide a value.

### Requirement 3: 招募广播发送

**User Story:** As a 研究人员, I want 选择目标渠道和联系人/群组来发送招募消息, so that 我可以触达潜在参与者并邀请他们参加研究。

#### Acceptance Criteria

1. WHEN a user initiates a broadcast, THE System SHALL require selection of: target channel, message template, and at least one recipient (group chat ID or user ID).
2. WHEN a broadcast is submitted, THE Recruitment_Broadcast SHALL create a Celery task that dispatches messages asynchronously via the selected Channel_Adapter.
3. THE Channel_Adapter SHALL use the vendored CowAgent channel implementation to call the IM platform API (feishu API or wecom webhook).
4. WHEN a broadcast is submitted for a Study, THE System SHALL automatically generate a StudyLink (if none exists) and inject it into the message template as {{study_link}}.
5. THE Recruitment_Broadcast SHALL support sending to multiple recipients (up to 50 per broadcast) in a single operation.
6. WHILE a broadcast is in progress, THE System SHALL display a progress indicator showing sent/total count.
7. IF a message delivery fails for a specific recipient, THEN THE Delivery_Record SHALL log the failure reason and THE System SHALL continue delivering to remaining recipients.

### Requirement 4: 投递状态追踪与反馈

**User Story:** As a 研究人员, I want 查看每条招募消息的投递状态, so that 我可以了解哪些消息成功送达、哪些失败，并采取补救措施。

#### Acceptance Criteria

1. THE Delivery_Record SHALL track each message with status: pending, sent, failed, or delivered.
2. WHEN a message is successfully sent to the IM platform API, THE Delivery_Record SHALL update status from "pending" to "sent" with a timestamp.
3. IF the IM platform returns a delivery confirmation callback, THEN THE Delivery_Record SHALL update status from "sent" to "delivered".
4. IF a message send fails after 3 retry attempts, THEN THE Delivery_Record SHALL mark status as "failed" and record the error detail.
5. WHEN a user views the broadcast detail page, THE System SHALL display a summary: total messages, sent count, delivered count, failed count, with the ability to expand and see individual recipient statuses.
6. WHEN one or more deliveries fail, THE System SHALL offer a "retry failed" action that re-enqueues only the failed Delivery_Records.

### Requirement 5: 渠道健康监控

**User Story:** As a 研究团队管理员, I want 系统自动检测渠道连接状态, so that 我能在渠道失效时及时收到提醒并修复配置。

#### Acceptance Criteria

1. THE System SHALL perform a periodic health check (via Celery beat, every 30 minutes) on all active Channel_Configs by sending a lightweight ping to the IM platform API.
2. IF a health check fails for a channel, THEN THE System SHALL update the channel status to "error" and record the failure timestamp and reason.
3. WHEN a channel transitions from "active" to "error", THE System SHALL display a warning banner on the recruitment page indicating which channel is unhealthy.
4. WHEN a channel has been in "error" status for more than 2 consecutive checks, THE System SHALL send a notification to the Team admin (via the team Inbox surface (InboxItem.kind=channel_unhealthy)).
5. WHEN a previously errored channel passes a health check, THE System SHALL automatically restore its status to "active".

### Requirement 6: 新手引导与帮助

**User Story:** As a 首次使用 IM 招募功能的研究人员, I want 系统提供清晰的引导和帮助信息, so that 我能在没有技术支持的情况下独立完成首次配置和发送。

#### Acceptance Criteria

1. WHEN a user accesses the IM recruitment feature for the first time (no Channel_Config exists for the Team), THE System SHALL display an onboarding wizard with three steps: "选择渠道类型" → "填写凭证" → "发送测试消息".
2. THE Config_Wizard SHALL include inline help tooltips for every credential field, explaining in plain language what the field is and where to find it (e.g., "在飞书开放平台 → 应用凭证页面复制 App ID").
3. THE System SHALL provide a "快速开始" documentation link on the recruitment page that opens a step-by-step guide with screenshots for each supported channel type.
4. WHEN a user completes the onboarding wizard successfully, THE System SHALL display a congratulatory message and offer to "发送第一条招募消息" as the next action.
5. IF a user encounters an error during onboarding, THEN THE System SHALL display a contextual troubleshooting suggestion (e.g., "请确认机器人已被添加到目标群组" for feishu permission errors).
6. THE System SHALL provide example recipient IDs (with format hints) for each channel type so users understand the expected input format (e.g., "群组 ID 格式: oc_xxxxxxxx").

### Requirement 7: 权限与安全

**User Story:** As a 团队管理员, I want 控制谁可以配置渠道和发送广播, so that 敏感的渠道凭证和群发能力不会被滥用。

#### Acceptance Criteria

1. THE System SHALL restrict channel configuration (create/edit/delete) to users with Team admin role.
2. THE System SHALL allow broadcast sending to users with Team admin or Team member role.
3. THE Channel_Config SHALL encrypt all secret fields (app_secret, token, webhook_url) using Django's Fernet encryption before database storage.
4. WHEN a non-admin user views the channel configuration page, THE System SHALL mask secret fields (showing only last 4 characters) and disable edit controls.
5. THE System SHALL enforce a rate limit of 100 messages per channel per hour to prevent abuse and comply with IM platform rate limits.
6. WHEN the rate limit is reached, THE System SHALL queue remaining messages and display a notice: "已达到发送频率限制，剩余消息将在下一小时自动发送".
