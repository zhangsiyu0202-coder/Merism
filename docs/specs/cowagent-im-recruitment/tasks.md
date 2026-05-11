# Implementation Tasks

## Task 1: Vendored Channel Adapters
- [x] 1.1 Create `products/studies/backend/recruitment/channels/__init__.py`
- [x] 1.2 Create `products/studies/backend/recruitment/channels/base.py` with `IMChannelBase`, `IMMessage`, `SendResult` dataclasses
- [x] 1.3 Create `products/studies/backend/recruitment/channels/feishu_adapter.py` — extract send logic from CowAgent feishu_channel.py (tenant_access_token + send message API)
- [x] 1.4 Create `products/studies/backend/recruitment/channels/wecom_bot_adapter.py` — extract webhook send logic from CowAgent wecom_bot
- [x] 1.5 Create `products/studies/backend/recruitment/channels/factory.py` — adapter factory by channel_type string
- [x] 1.6 Write unit tests for adapters with mocked HTTP responses

**Depends on:** nothing
**Refs:** Requirement 3 (AC 3), Design §1

## Task 2: Django Models + Migration
- [x] 2.1 Add `ChannelConfig` model with Fernet encrypted credentials field
- [x] 2.2 Add `MessageTemplate` model with placeholder validation
- [x] 2.3 Add `RecruitmentBroadcast` model linked to Study + ChannelConfig
- [x] 2.4 Add `DeliveryRecord` model with status tracking
- [x] 2.5 Create Django migration (all 4 models, `merism_` table prefix)
- [x] 2.6 Create data migration seeding 3 built-in templates ("简洁邀请", "详细说明", "紧急招募")
- [x] 2.7 Add `MERISM_IM_RECRUITMENT` feature flag to `posthog/settings/web.py`

**Depends on:** nothing
**Refs:** Requirement 1 (AC 1), Requirement 2 (AC 1), Design §2

## Task 3: Credential Encryption Utilities
- [x] 3.1 Create `products/studies/backend/recruitment/crypto.py` with `encrypt_credentials()` and `decrypt_credentials()` using Fernet derived from SECRET_KEY
- [x] 3.2 Write tests for encrypt/decrypt round-trip and tamper detection

**Depends on:** Task 2
**Refs:** Requirement 7 (AC 3), Design §5

## Task 4: Celery Tasks for Broadcast Dispatch
- [x] 4.1 Implement `dispatch_recruitment_delivery` task — load broadcast, decrypt creds, instantiate adapter, send per recipient, update DeliveryRecord
- [x] 4.2 Implement `sync_cowagent_channel_mirror` task — periodic health check for all active channels
- [x] 4.3 Implement `retry_failed_deliveries` task — re-enqueue failed DeliveryRecords
- [x] 4.4 Register `sync_cowagent_channel_mirror` in Celery beat schedule (every 30 min)
- [x] 4.5 Add rate limiting logic (100 msg/hour/channel via Redis sliding window)
- [x] 4.6 Write tests for task logic with mocked adapters

**Depends on:** Task 1, Task 2, Task 3
**Refs:** Requirement 3 (AC 2, 5, 7), Requirement 4 (AC 4, 6), Requirement 5 (AC 1-5), Design §3, §6

## Task 5: REST API Endpoints
- [x] 5.1 Create `ChannelConfigSerializer` with credential masking for non-admin
- [x] 5.2 Create `ChannelConfigViewSet` (CRUD + test endpoint)
- [x] 5.3 Create `MessageTemplateSerializer` with placeholder validation
- [x] 5.4 Create `MessageTemplateViewSet` (CRUD + preview endpoint)
- [x] 5.5 Create `RecruitmentBroadcastSerializer` with auto StudyLink generation
- [x] 5.6 Create `RecruitmentBroadcastViewSet` (list/create/detail + retry endpoint)
- [x] 5.7 Register URL routes under `/api/studies/`
- [x] 5.8 Add permission checks (admin-only for channel config, member+ for broadcast)
- [x] 5.9 Write API tests

**Depends on:** Task 2, Task 3, Task 4
**Refs:** Requirement 1 (AC 3-5), Requirement 3 (AC 1, 4), Requirement 7 (AC 1-2, 4), Design §4

## Task 6: Template Rendering Engine
- [x] 6.1 Create `products/studies/backend/recruitment/renderer.py` — render template with context variables, validate required placeholders
- [x] 6.2 Implement format adaptation (Markdown → feishu interactive card JSON; Markdown → wecom markdown)
- [x] 6.3 Write tests for rendering with missing variables, edge cases

**Depends on:** Task 2
**Refs:** Requirement 2 (AC 2-6), Design §1

## Task 7: Frontend - Channel Config Wizard (optional, can be deferred)
- [x] 7.1 Create `ChannelConfigWizard` component (3-step: select type → fill creds → test)
- [x] 7.2 Add inline help tooltips with platform-specific guidance
- [x] 7.3 Create `ChannelStatusIndicator` component (green/red/yellow)
- [x] 7.4 Wire to REST API

**Depends on:** Task 5
**Refs:** Requirement 1 (AC 2, 4, 5), Requirement 6 (AC 1-6), Design §7

## Task 8: Frontend - Broadcast Composer (optional, can be deferred)
- [x] 8.1 Create `BroadcastComposer` page (select channel → select template → preview → add recipients → send)
- [x] 8.2 Create `TemplatePreview` component with live variable interpolation
- [x] 8.3 Create `DeliveryStatusPanel` with progress bar and per-recipient status
- [x] 8.4 Wire to REST API

**Depends on:** Task 5, Task 7
**Refs:** Requirement 3 (AC 1, 6), Requirement 4 (AC 5), Design §7

---

## Execution Order (recommended)

1. Task 1 (adapters) + Task 2 (models) — 可并行
2. Task 3 (crypto) + Task 6 (renderer) — 可并行
3. Task 4 (Celery tasks)
4. Task 5 (API)
5. Task 7 + Task 8 (frontend) — 可延后
