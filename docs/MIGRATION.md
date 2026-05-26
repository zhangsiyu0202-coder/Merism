# Migration map — where each module came from

Quick reference for tracing any `merism-app/` file back to its source in
the old `posthog-foss` cutover repo. Useful when comparing behavior or
hunting for a missing helper.

## Ported verbatim (no logic changes)

| merism-app/ | source in old repo |
|---|---|
| `merism/testing/` | `merism/testing/` (created in this session's Phase B.5) |
| `merism/recruitment/adapters/base.py` | `products/studies/backend/recruitment/channels/base.py` |
| `merism/recruitment/adapters/feishu_adapter.py` | `products/studies/backend/recruitment/channels/feishu_adapter.py` |
| `merism/recruitment/adapters/wecom_bot_adapter.py` | `products/studies/backend/recruitment/channels/wecom_bot_adapter.py` |
| `merism/recruitment/adapters/qq_group_adapter.py` | `products/studies/backend/recruitment/channels/qq_group_adapter.py` |
| `merism/recruitment/adapters/qq_guild_adapter.py` | `products/studies/backend/recruitment/channels/qq_guild_adapter.py` |
| `merism/recruitment/renderer.py` | `products/studies/backend/recruitment/renderer.py` |
| `merism/recruitment/rate_limit.py` | `products/studies/backend/recruitment/rate_limit.py` |
| `merism/recruitment/builtin_templates.py` | `products/studies/backend/recruitment/builtin_templates.py` |
| `docs/PRODUCT.md` | `standalone/PRODUCT.md` |
| `docs/specs/cowagent-im-recruitment/` | `.kiro/specs/cowagent-im-recruitment/` |
| `docs/specs/merism-design-system/` | `.kiro/specs/merism-design-system/` |
| `docs/specs/merism-platform/` | `.kiro/specs/merism-platform/` |

## Ported with minor rewrites

| merism-app/ | source in old repo | rewrite |
|---|---|---|
| `merism/recruitment/adapters/factory.py` | `products/studies/backend/recruitment/channels/factory.py` | Imports `merism.recruitment.adapters.*` instead of `products.studies.backend.recruitment.channels.*` |
| `merism/recruitment/crypto.py` | `products/studies/backend/recruitment/crypto.py` | Prefers `settings.MERISM_CHANNEL_ENCRYPTION_KEY` env var, falls back to PBKDF2-on-SECRET_KEY for dev convenience |

## Written from scratch (reference spec — not old repo)

| merism-app/ | reference |
|---|---|
| `pyproject.toml` | Old repo had one huge `pyproject.toml` for a 50-product monorepo. This one lists only what Merism itself uses. |
| `merism/settings/{base,dev,test,prod}.py` | Old repo's `posthog/settings/` sprawled across 20+ files. This is a clean four-file split. |
| `merism/urls.py` | Old `posthog/urls.py` had ~100 route groups. This is ~8 lines + per-domain includes. |
| `merism/apps.py` | Single-app project; no sub-app fragmentation. |
| `merism/models/team.py` | Native `merism.Team`. Old repo used `posthog.Team` for everything — we deliberately do NOT. |
| `merism/models/study.py` | Follows platform spec Req 1-10. Old repo had both `Study.research_goal` field AND a `StudyGoal` multi-goal flat list; spec Req 21.3/21.4 says drop the flat list, so we did. |
| `merism/models/interview.py` | Follows platform spec Req 4/9-15. New `Participation.is_preview` column (Req 8). `InterviewSession.audio_s3_key` kept as empty by convention (Req 12.4 — voice mode never persists audio). |
| `merism/models/knowledge.py` | L1 / L2 KB split per spec Req 19. `pgvector.django.VectorField` imported with sqlite JSONField fallback so tests run on sqlite. |
| `merism/models/recruitment.py` | Per IM-recruitment spec Req 1-5. `credentials_encrypted` is a binary blob, never plaintext. `ChannelHealthCheck` is new (append-only probe log). |
| `merism/models/report.py` | Per platform spec Req 16-19. `StudyReport.blocks` JSONField validated by the Pydantic v2 schema at `merism/reports/schema.py` (R7). |
| `merism/models/memory.py` | MEM AI state. Scoped to `merism.Team` (not `posthog.Team`). |
| `merism/tests/test_boundary.py` | New boundary enforcement. Asserts zero `posthog.*` loaded. |
| `bin/setup-dev.sh` | Written fresh. Old repo had many flox-specific scripts — this has no flox dep. |
| `docker-compose.yml` | Strip old repo's ClickHouse / Kafka / Temporal services. |

## Deliberately NOT ported (per spec)

These existed in the old repo but the spec says drop them:

| NOT ported | why |
|---|---|
| `merism/conductor/macro.py` (LangGraph 3-layer graph) | Platform spec Req 14.7 — moderator is a **2-node sequential pipeline** (`coverage_steer → generate`, both inside one `stream_turn` coroutine), not macro/meso/micro |
| `products/studies/backend/conductor/policies/` (coverage_steer, engagement, off_topic) | Platform spec Req 21.5 — defer policies until 100+ real interviews inform the design |
| `merism/memai/tools/{execute_sql, create_insight, upsert_dashboard, call_mcp_server, create_form, create_notebook, list_data, read_data, read_data_warehouse_schema, read_taxonomy, search}.py` | None are Merism features — these are PostHog-product-specific tools |
| `merism/memai/core/agent_modes/presets/{product_analytics, session_replay, error_tracking, flags, survey, llm_analytics, sql}.py` | All map 1:1 to PostHog products |
| `merism/memai/chat_agent/rag/nodes.py` | Depends on `posthog.hogql_queries` — will be replaced with a Merism-native retrieval node in R8 |
| `merism/memai/chat_agent/memory/nodes.py` (PostHog taxonomy onboarding) | The onboarding questions were "what events do you track?" — Merism's equivalent is "what research are you running?", which is a different flow |
| `merism/memai/chat_agent/slash_commands/commands/usage/` | Queries PostHog billing — Merism has its own usage model |
| `merism/memai/insights_assistant.py` | Generates PostHog Insight (Trends/Funnels/Retention) — Merism has no Insight concept |
| `posthog/*`, `ee/*`, `products/{alerts,analytics_platform,batch_exports,cdp,...}` | 50+ PostHog-origin products — not Merism's scope |
| `plugin-server/` | ADR 0001 — behavior triggers run in Celery beat, not Node plugin server |
| `.flox/` | Downgraded to optional in old repo's Phase A; not needed in new repo at all |
| `posthog/test/base.py` and 51 tests that import from it | Replaced by `merism.testing` (Phase B.5) |

## Deliberate deviations from PRODUCT.md §6

PRODUCT.md was written while the old `posthog-foss` cutover was still the
target repo, so some lines reference PostHog-internal abstractions that we
can't preserve in the clean-slate `merism-app/`. Deviations:

| PRODUCT.md says | merism-app does | Why |
|---|---|---|
| "对象存储: PostHog object_storage (S3 抽象)" | `boto3` against S3 / MinIO directly, configured via `OBJECT_STORAGE_*` env vars | PostHog's `object_storage` module depends on its Django app graph. Rolling our own thin wrapper is a few dozen lines; keeping a PostHog dep just for storage is not worth it. |
| "所有 LLM 调用通过 `posthoganalytics.ai.openai` 包装" | `openai.OpenAI` with DeepSeek `base_url`; optional `posthoganalytics` Python SDK (pypi package — **not** the `posthog.*` Django app) can be added as a trace/cost instrumentation wrapper in `merism.memai.llm` without violating the no-PostHog rule. | `posthoganalytics` the SDK is a separate, pip-installable package. If cost tracking is a hard requirement we add it; otherwise defer. |

## Shape fix (applied 2026-05-10)

`StudyReport.blocks` → `StudyReport.content` + `StudyReport.charts`. The
earlier `blocks` flat-list representation didn't match PRODUCT.md §4 or
`merism-platform` Req 17. The lower-level block schema (text/metric/quote/
chart blocks) still exists — it's now the format of things INSIDE each
panel of `content`, validated by `merism.reports.schema` (R7).



## If you need a file that's not here

Check the "NOT ported" list above first — if it's there, there's a spec
reason not to carry it over.

If it's not there, and you genuinely need it, grep the old repo:
```bash
cd /home/jia/posthog-foss     # old repo
rg --files | grep <keyword>
```
and add a corresponding row to this table when you port it.

## R15 runtime harness additions (2026-05-11)

Entirely new to Merism — no old-repo provenance. See
`docs/RUNTIME.md` for the architecture writeup.

| File | Role | Migration |
|---|---|---|
| `merism/models/session_event.py` | Append-only turn log | `0009_sessionevent` |
| `merism/models/invitation.py` | Per-recipient token + trace_id | `0011_studylink_require_invitation_invitation` |
| `merism/models/inbox.py` | Researcher-facing notifications | `0013_inboxitem` |
| `merism/conductor/event_log.py` | Append / replay service | — |
| `merism/conductor/closure.py` | 6-signal closure + orphan cleanup | — |
| `merism/conductor/study_closure_signal.py` | Auto-close on target reached | — |
| `merism/conductor/inbox_signals.py` | InboxItem post_save writers | — |
| `merism/observability.py` | `bind_trace` structlog context manager | — |
| `merism/api/interview_message_view.py` | Text-mode SSE turn endpoint | — |
| `merism/voice/processors/moderator.py` | `ModeratorLLMProcessor` (replaces `LLMProcessor` when guide present) | — |
| `frontend/src/features/interview/TextInterviewPage.tsx` + logic | Text-mode participant UI | — |
| `frontend/src/features/inbox/*` | Inbox page + logic | — |
| `merism/participant/views.py` | Invitation-aware resolve; preview bypass; auto-close disambiguation | — |
| `merism/recruitment/tasks.py` | `_delivery_context` creates Invitation + stamps trace_id; `dispatch_pending_broadcasts` catch-up | — |

Field additions (non-model files):

| Table | New column | Migration |
|---|---|---|
| `merism_participation` | `trace_id: UUIDField(default=uuid4, indexed)` | `0010_*` |
| `merism_participation` | `completed_at: DateTimeField(null)` | `0012_*` |
| `merism_interview_session` | `trace_id: UUIDField(null, indexed)` | `0010_*` |
| `merism_delivery_record` | `trace_id: UUIDField(null, indexed)` | `0010_*` |
| `merism_session_insight` | `trace_id: UUIDField(null, indexed)` | `0010_*` |
| `merism_study_link` | `require_invitation: BooleanField(default=False)` | `0011_*` |

---

## R17-R26 新增表 / 模块（2026-05-12 至 2026-05-19）

R15 之后又陆续加了一批新功能。完整迁移清单（0014-0032）：

| 迁移 | 内容 |
|---|---|
| 0014 | LLM gateway 观测 schema（后被 0023 替代/重塑）|
| 0015 | `StudyLink.short_link_domain` |
| 0016 | Cross-session analysis 模型：`StudyGoal` / `Theme` / `CoverageSnapshot` / `CohortSegment` |
| 0017 | `Glossary`（ASR 修正词表）|
| 0018 | Codebook 治理：`CodebookVersion` / `CodeChange` / `CodeMapping` |
| 0019 | `ChannelTarget`（独立群发目标 + ChannelConfig.email enum）|
| 0020 | Link tracking：`LinkClick` / `LinkShareEvent` |
| 0021 | Insights & Custom Reports（6 张表）|
| 0022 | `SessionEvent` 增加 `question_id` / `turn_number` 列 |
| 0023 | `ServiceSettings`（每团队 LLM/TTS/STT/Embedding 配置 + 加密 api_key）|
| 0024 | `Conversation.messages` JSONField |
| 0025 | `Invitation.bound_browser_token` |
| 0026 | `AskArtifact` 雏形 |
| 0027 | `Invitation.uses_left` / `valid_from` |
| 0028 | `StudyLink.link_mode`（anonymous / named）|
| 0029 | `Study.status` 从 6 状态简化到 3（draft / live / closed）|
| 0030 | Study.status 数据迁移（旧 status → 新 3 状态映射）|
| 0031 | `AskArtifact` 重建（schema 调整）|
| 0032 | `Conversation.messages` schema fine-tune |

## 新模块来源

| `merism-app/` 新模块 | 出处 | 备注 |
|---|---|---|
| `merism/voice/` | 全新（pipecat 风格自实现，BSD-2 思想，无代码引用）| Frame/Pipeline/Processor 三层抽象；ADR 0002 barge-in |
| `merism/conductor/{decision_prompt,generation_prompt,probe_blocks,decision_validator,closure,event_log}.py` | 全新（R15 + R23）| 2-node moderator + 6 信号 closure |
| `merism/cleaning/` | 全新（R17）| 多阶段转写清洗 |
| `merism/codebook/` | 全新（R16）| 治理 4 agent + version_manager |
| `merism/concept/` | 全新（R14.1）| Concept Testing 2.0 |
| `merism/analysis/` | 全新（R22）| Themes + Coverage + Cohort |
| `merism/llm_gateway/` | 全新（R18）| 团队级路由 |
| `merism/services/configuration/` | 全新（R18）| Dograh 风格 service registry |
| `merism/recruitment/adapters/email_adapter.py` | 全新（R19）| SMTP / MCP 双形态 |
| `merism/recruitment/orchestrator.py` | 全新 | 群发流水编排 |
| `merism/recruitment/participant_email_recruitment.py` | 全新（R19）| 受访者邮件邀请 |
| `merism/participant/link_tracking.py` | 全新（R20）| Dub.co 风格 click 记录 |
| `merism/participant/funnel.py` | 全新 | 漏斗统计 |
| `merism/api/{insights_views,insights_tasks,ask_views,conversation_views,interview_message_view,link_tracking_views,analysis_views,cleaning_views,home,users}.py` | 全新（R12-R25）| 各域 viewset / 端点 |
| `merism/memai/agents/{outline_review,recruitment_message,quote_extractor,quote_tagger,session_insight_generator,study_narrative_summary,inductive_code_suggester,codebook_seeder,codebook_reviewer,analysis}.py` | 全新（R12-R25）| 12+ agents |
| `merism/memai/title_generator.py` | 全新（R25）| Conversation 异步起标题 |
| `merism/memai/graph/` | 全新 | LangGraph 风格 graph helpers |
| `frontend/src/features/{home,studies,ask,inbox,repository,assistant,analysis,interview,participant,sessions,settings,authentication,welcome}/` | 全新（R9 + R14）| 14 个 Scene |
| `frontend/src/lib/merism/{primitives,patterns,tokens,illustrations,fonts}/` | 全新（R14）| Outset-grade 设计系统 |

## 与 PRODUCT.md 不再冲突的描述

PRODUCT.md 已更新到 2026-05-20 版本，以下旧"deviations"已不再适用：

| 旧描述 | 现状 |
|---|---|
| "对象存储：PostHog object_storage" | 已删，PRODUCT.md §6 写明 boto3 / MinIO |
| "所有 LLM 调用通过 posthoganalytics.ai.openai" | 已删，PRODUCT.md §6 写明 `merism.llm_gateway.client.get_client` 路由 |
| "Email / SMS 非 MVP" | Email 已 MVP（R19）；SMS 仍延后 |
| "单 LLM 调用同时返回 (text, next_action)" | 已改为 2-node（R23）；AGENTS.md 规则 4 + spec Req 14 已在 2026-05-20 同步 |
| "Study.status 6 状态" | 已简化到 3 状态（迁移 0029） |

> 修订记录：**2026-05-20** —— 追加 R17-R26 迁移与新模块清单；删除已修复的 deviations。
