# Merism rebuild roadmap

最后更新：**2026-05-23**（R29 v1 retirement）。本文档记录 `merism-app/` 重建工作每一轮的内容、状态与下一步。

格式：每个里程碑（R*）独立小节，开头标 ✅ / ⏳ / 🔭，越靠下越近期完成。文末列出"下一阶段候选"。

---

## 当前状态速览（2026-05-20）

| 维度 | 数值 |
|---|---|
| Django 模型 | 56 |
| 迁移文件 | 32 |
| 后端测试 | 295（test collection），test_boundary 5/5 全过 |
| 前端测试 | 39 vitest + 0 oxlint + 0 typescript 错误 |
| 前端 Scenes | 14 |
| Study sub-tabs | 9 |
| 后端 ViewSets | 35+ |
| 招募 channel adapters | 6（feishu / wecom / wecom_bot / qq_group / qq_guild / email）|

主流功能链路（invite → consent → 访谈 → 闭包 → 分析 → 报告 → Inbox）端到端可走通，含语音 / 文本两路。

---

## ✅ R1-R10 — Bootstrap & 骨架（已完成）

### R1 — 项目脚手架
- `pyproject.toml`（Python 3.12.12 / Django 5.2 / DRF / pgvector / Pydantic v2 / cryptography / openai / langchain-core / structlog）
- `README.md`、`AGENTS.md`、`docker-compose.yml`（pg + redis + minio）
- `bin/setup-dev.sh`、`bin/postgres-init.sql`
- `manage.py`、`.gitignore`、`.env.example`、`pytest.ini`、`conftest.py`

### R2 — Django 项目骨架
- `merism/{__init__,apps}.py`
- `merism/settings/{__init__,base,dev,test,prod}.py`（prod 强校验环境变量）
- `merism/{urls,wsgi,asgi}.py`

### R3 — 测试 harness
- `merism/testing/`（24 文件：factories / fakes / assertions / fixtures / freezetime / pytest_plugin）
- `merism/tests/test_boundary.py` —— `DJANGO_SETTINGS_MODULE`、零 PostHog、INSTALLED_APPS 白名单

### R4 — 核心模型 27 张（已扩展到 56 张，见 R14+）
最初拉起 27 张表的 5 个域模型 + 测试 fixture。后续 R14-R16 大幅扩张到 56 张。

### R6 — IM 渠道移植
- `merism/recruitment/adapters/{base,feishu_adapter,wecom_bot_adapter,qq_group_adapter,qq_guild_adapter,factory}.py`
- `merism/recruitment/crypto.py`（Fernet, 优先 `MERISM_CHANNEL_ENCRYPTION_KEY`，回退 PBKDF2）
- `merism/recruitment/renderer.py` / `rate_limit.py`（100 msg/channel/h）/ `builtin_templates.py`

### R7 — 报告 Block Schema
- `merism/reports/schema.py` —— Pydantic v2：TextBlock / QuoteBlock / MetricBlock / ChartBlock / BlocksDocument / StudyReportContent（4-panel）/ ChartSpec / Citation / CustomReportAnswer
- 18 测试覆盖 atom / discriminator / panel rejects

### R8 — 各域骨架
| 包 | 完成 |
|---|---|
| `merism/api/` | `base.py`（TeamScopedModelViewSet）+ 22 serializer + 17 viewset + 10 @actions |
| `merism/conductor/` | `state.py` / `prompts.py` / `moderator.py`（最初的单调用版本）/ `guide_cursor.py` |
| `merism/memai/` | `tool.py` + `llm.py`（Langfuse 自动注入，无 key 时 noop） |
| `merism/knowledge/` | `citations.py` / `search.py`（pgvector + ts_rank_cd + RRF k=60）/ `embeddings.py` |
| `merism/realtime/` | SSE + WebSocket 雏形 |
| `merism/recruitment/tasks.py` | dispatch / retry / health_check 三个 Celery 任务 |

### R9 — 前端 bootstrap + design system
- React + Vite + TS + Kea
- `frontend/src/lib/merism/` —— tokens / primitives / patterns（详见 R14）
- 14 个 Scene + 7 个 study tab 雏形

### R10 — docs 拉起
- `docs/PRODUCT.md` / `docs/ROADMAP.md` / `docs/MIGRATION.md` / `docs/RUNTIME.md`
- `docs/specs/{cowagent-im-recruitment,merism-design-system,merism-platform}/`
- `docs/adr/`（ADR 0001+）

---

## ✅ R11 — 验证与 CI（已完成）

```
bin/setup-dev.sh             # 一键启动
pytest merism/tests          # 全 boundary smoke
python manage.py check       # 0 错误
ruff check merism            # 0 lint
pyright merism               # 0 type
```

---

## ✅ R12-R13 — API 完整 + 实时层（已完成）

- 22 serializer / 17 viewset / 10 @actions（launch / close / finalize / search / test / send / retry 等）
- SSE：`merism/realtime/sse_interview.py`（Redis Streams + Last-Event-ID 回放 + 15s heartbeat + 5000 maxlen）
- WebSocket：`merism/realtime/voice.py` + `voice_protocol.py`（Pydantic 严格消息 + ADR-0002 barge-in）

---

## ✅ R14 — Outset-grade UX 升级（已完成 2026-05-10）

8 条线，详细记录见 `docs/.archive_2026-05-20/ROADMAP.md` 中的 R14 段。要点：

### R14.1 — Concept Testing 2.0
- `Concept` / `ConceptBlock` / `ConceptRotationCursor`，3 种 rotation 策略
- `concept_plan.expand_guide()` 纯函数 + `moderator._expand_if_needed`
- `StimulusShowFrame` 通过 voice pipeline 推前端 crossfade
- Dimensions scorer：sentiment / purchase_intent / appeal / comprehension

### R14.2 — Design tokens（8pt grid + Slate + Stripe alpha-core tag）
- 10-tier 排版（hero 72 → caption 12）
- Radii xs 4 → 2xl 24
- Elevation `shadow-merism-{xs,sm,card,float,pop}`
- Hairline `--merism-hairline`
- Tag 同色 alpha-core（neutral / accent / success / warning / danger / info）
- 全局 6px 滚动条
- `bin/align_8pt.py` 可重跑迁移脚本

### R14.3 — 新增 / 重写 primitives 与 patterns
PageTopBar / PageHeading / KpiCard / KpiGrid / ExecutiveSummary / SettingsSection / OrderedList / ThreePaneLayout / LogicCard / LiveSummaryPanel / Illustration / ChatPanel / Tag …

### R14.4 — Sidebar 四区
WorkspaceAnchor / 平铺实体导航 / PinnedStudies / UserBadge

### R14.5 — Home Scene
5-列 KpiGrid + Studies 横排 + FirstStudyHero（`GET /api/home/stats/`）

### R14.6 — Settings + 模型变更
- `Study.research_objectives: JSONField(default=list)` + 迁移 0004
- 安全修复：`TeamScopedModelViewSet.perform_create` 永远注入 team

### R14.7 — Per-page 子导航 + 插画
所有 7 个顶层页接 `PageTopBar`

### R14.8 — Header 紧凑（节省每屏 ~80px）

收尾验证：`pytest 59 passed + 1 skipped` / `vitest 37 passed` / build < 5s。

---

## ✅ R15 — 运行时编排 + 端到端自动化（已完成 2026-05-11）

R15 的 8 个步骤把"链接发出 → 受访者完成 → 研究者收到分析"全链路串起来。详见 [`RUNTIME.md`](RUNTIME.md)。

| 步骤 | 内容 | 迁移 |
|---|---|---|
| R15.0 | `SessionEvent` 事件日志（append-only，per-session 单调 seq）+ `event_log.py` 服务 | 0009 |
| R15.1 | `trace_id` 横贯 7 张表 + `observability.bind_trace` + admin Trail view | 0010 |
| R15.2 | `Invitation` 模型 + `StudyLink.require_invitation` + 单次令牌链路 | 0011 |
| R15.3 | 文本模式 SSE 回合：`POST /api/sessions/<id>/message/` + cookie 鉴权 + frontend `TextInterviewPage` | — |
| R15.4 | 6 信号 closure（`closure.py`）+ `abandon_stuck_sessions` Celery beat | 0012 |
| R15.5 | `Study.actual_completed_count` 改 `@property`（aggregate）+ auto-close 信号 + study_full vs link_closed 区分 | — |
| R15.6 | `InboxItem` + 3 个 post_save signal + 前端 `InboxPage` 重写 | 0013 |
| R15.7 | `ModeratorLLMProcessor` —— voice pipeline 接入 `stream_turn`，替代默认 LLMProcessor | — |
| R15.8 | `process_completed_session` 切成 Celery `chain`（polish → extract_and_tag → index_and_insight）+ `dispatch_pending_broadcasts` 60s catch-up | — |

收尾：`pytest 211 passed + 1 skipped`（+57 vs R14）；`merism/tests/test_e2e_automation.py` 1 个用例完整走通 invite→inbox 链路 (mocked LLM, < 6s)。

---

## ✅ R16 — Codebook 治理（后端完成，前端 UI 待做）

- 设计文档：`docs/specs/codebook-governance/design.md`
- 数据模型：`CodebookVersion` / `CodeChange` / `CodeMapping` —— 迁移 0018
- 4 个 agent：`InductiveCodeSuggester` / `CodebookReviewer` / `CodebookVersionManager` / `RetaggingJob`
- `merism/codebook/saturation.py` 触发 ThemeSynthesizer
- 集成进 `conductor.post_session.py` 第 5 步
- ⬜ 前端：codebook 版本历史 + 提议 approve/reject UI
- ⬜ Admin：CodebookVersion / CodeChange 浏览界面

---

## ✅ R17 — Cleaning pipeline + Glossary（已完成）

多阶段转写清洗，每阶段独立可关：

```
stage1_asr_correct (Glossary 替换)
   ↓
stage3_normalize (NFKC + 中英混排归一)
   ↓
rule_clean (filler 词正则)
   ↓
llm_polish (批量 LLM)
   ↓
stage6_semantic_merge (可选 opt-in)
```

模型：`Glossary`（团队级 / 单 study 级，迁移 0017）；编排：`merism/cleaning/pipeline.py`。

---

## ✅ R18 — LLM Gateway + ServiceSettings（已完成）

- 迁移 0014：LLM 调用观测 schema（之前的 ad-hoc 表，后被 0023 取代）
- 迁移 0023：`ServiceSettings`（每团队 LLM/TTS/STT/Embedding 配置；加密 api_key）
- `merism/llm_gateway/client.py` —— 统一 `get_client(logical_name, *, team, trace_id)`：team ServiceSettings 优先，回退环境变量
- `merism/services/configuration/{factory,registry}.py` —— Dograh 风格 service registry

---

## ✅ R19 — Channel Target + Email 渠道（已完成）

- 迁移 0019：`ChannelTarget`（独立群发目标）
- `merism/recruitment/adapters/email_adapter.py` —— SMTP / MCP 双形态
- `merism/recruitment/participant_email_recruitment.py` —— 受访者邮件邀请
- `merism/management/commands/send_participant_email_recruitment.py`
- `ChannelType.EMAIL` 加入枚举
- 6 测试覆盖 email_adapter + participant_email_recruitment

---

## ✅ R20 — Link tracking（Dub.co 风格，已完成）

- 迁移 0020：`LinkClick` + `LinkShareEvent`
- `merism/participant/link_tracking.py` —— `_identity_hash(ip, ua)` 1h 去重 + `referrer_participation` 链路
- `merism/api/link_tracking_views.py` —— LinkClickViewSet / LinkShareEventViewSet
- UTM 参数捕获 / device 解析 / Geo（IP-lookup 可选）
- `StudyLink.clicks` 计数器原子 `F() + 1` 更新

---

## ✅ R21 — Insights / Custom Reports（已完成）

迁移 0021：

**Insights（auto-generated）**
- `StudyInsights`（status 状态机：pending → generating → ready → failed）
- `InsightHighlight`（3-6 张 headline + summary，可选跳转 finding）
- `InsightFinding`（chart_spec + chart_interpretation + themes + subthemes + insight_nuggets + supporting_evidence）

**Custom Reports（user-created）**
- `CustomReport`（含 `share_token` + `is_public` + `/shared/report/<token>/` 公开 URL）
- `ReportSegment`（人群子集，selector 跟 CohortSegment 同形）
- `ReportQuestion`（每问题独立 AI 分析；question_type 5 种；可绑 segment）

API：`StudyInsightsViewSet` / `InsightHighlightViewSet` / `InsightFindingViewSet` / `CustomReportViewSet` / `ReportSegmentViewSet` / `ReportQuestionViewSet` + `shared_report_view`。

任务：`merism/api/insights_tasks.py`（generate_study_insights / generate_custom_report_question）。

前端：`features/analysis/InsightsPage.tsx` / `ReportsListPage.tsx` / `ReportDetailPage.tsx` / `AnalysisChart.tsx`。

---

## ✅ R22 — 跨 session 分析（Themes / Coverage / Cohort，已完成）

迁移 0016：

- `StudyGoal`（结构化研究问题，priority P0/P1/P2，coverage 0..1，is_answered）
- `Theme`（HDBSCAN 聚类，centroid_embedding 增量分配，session_count / quote_count / sentiment_mix）
- `CoverageSnapshot`（每场结束后重建，按优先级加权）
- `CohortSegment`（人群子集，selector）

实现：`merism/analysis/themes/{embedder,clusterer,theme_matcher,theme_summarizer}.py` + `merism/analysis/coverage/goal_coverage.py` + `merism/analysis/pipeline.py:rebuild_study_analysis`。

API：`StudyGoalViewSet` / `ThemeViewSet` / `CoverageSnapshotViewSet` / `CohortSegmentViewSet`。

---

## ✅ R23 — Conductor 2-node pipeline（已完成 2026-05-18）

> ⚠️ **架构变更**：从单 LLM call 改成 `coverage_steer (decide) → generate (stream)` 顺序两节点。详见 `docs/PRODUCT.md` §5.2。

实现：
- `merism/conductor/decision_prompt.py` + `decision_validator.py` —— Node 1
- `merism/conductor/generation_prompt.py` —— Node 2
- `merism/conductor/probe_blocks.py` —— 动态探针定义
- `merism/conductor/adaptive_probing.py` —— `build_coverage_context`
- `merism/conductor/text_chunker.py` —— TTS 友好分句
- `merism/conductor/moderator_eval.py` —— 离线评测
- `merism/conductor/closure.py` —— 6 信号 + closing_grace 宽限期

⬜ 仍待：把 AGENTS.md 规则 4 + `docs/specs/merism-platform/requirements.md` Req 14.7 同步成 2-node 描述。

---

## ✅ R24 — Voice Pipeline pipecat-style（已完成 2026-05-18 / 19）

迁移：无（纯运行时）。

**Frame-based 架构**（`merism/voice/`）：

```
STTProcessor (Qwen Paraformer 流式)
   ↓ TranscriptionFrame
ModeratorLLMProcessor (接 conductor.stream_turn)
   ↓ LLMTextFrame (response_id)
TTSProcessor (Qwen CosyVoice 流式)
   ↓ TTSAudioRawFrame
ConversationState (OpenAI-Realtime-style truncation)
   ↓
UserIdleDetector (注入合成 turn)
```

- `merism/voice/frames.py` —— Frame 层级（System / Data / Control）
- `merism/voice/pipeline.py` —— Pipeline / PipelineTask / PipelineRunner / FrameProcessor 基类
- `merism/voice/observer.py` —— Composite / Metrics / Structlog / TranscriptRecorder
- `merism/voice/processors/{stt,llm,tts,conversation_state,user_idle,moderator}.py`
- `merism/realtime/voice.py` —— Channels WebSocket consumer
- `merism/realtime/voice_egress.py` —— 出栈 frame 序列化到 wire
- `merism/realtime/recording_observer.py` —— 录音落 S3
- ADR 0002 barge-in：PTT start → InterruptionFrame → TruncatedFrame → 修剪 ConversationState 已存的 assistant 回合

⬜ 仍待：网络丢帧自动重发；TTS sentence-level prefetch。

---

## ✅ R25 — Ask Merism 完整闭环（已完成）

迁移 0024 / 0026 / 0031 / 0032：

- `Conversation.messages: JSONField` 直接持久化（不再依赖 LangGraph checkpointer）
- `AskArtifact`（5 种 type，含 `short_id` 独立分享）
- `merism/api/ask_views.py` —— `ask_stream` SSE + `ask_title`
- `merism/api/conversation_views.py` —— Conversation CRUD（list / get / save / delete）
- 前端 `features/ask/`：AskPage + askLogic + ChartRenderer + CitationStrip
- `merism/memai/title_generator.py` 异步起标题
- `merism/memai/agents/study_narrative_summary.py` study summary artifact

---

## ✅ R26 — 受访者模式扩展 + StudyLink 简化（已完成）

迁移 0027 / 0028 / 0029 / 0030：

- `StudyLink.link_mode ∈ {anonymous, named}`（迁移 0028）
- `Study.status` 从 6 状态简化到 3 状态 `{draft, live, closed}`（迁移 0029 + 0030 数据迁移）
- `Invitation.uses_left` + `valid_from`（迁移 0027）
- `Invitation.bound_browser_token`（迁移 0025）

---

## ✅ R27 — Conductor v2 list interpreter (deleted 2026-05-23, superseded by R28)

实施 2026-05-21 / 22, 删除 2026-05-23. ADR 0009 落地了 list interpreter 架构 (~2150 LOC + 150 tests, 含 schema/engine/event_log/router/text_runner/sse_sink/voice_sink/ai_clients/persistence + 前端 V2AdvancedSection 折叠面板), 一天内 dogfeed 即判定 typed slots / skip_if / behavior_slots 抽象不必要, 砍掉重写为 LangGraph (R28). v2 上线期间 0 个生产 session 跑过.

---

## ✅ R28 — Conductor v3 LangGraph (实施 + 简化 2026-05-23)

ADR 0012 落地. 抛弃 v2 list interpreter + 全部 typed slots / skip_if / behavior_slots 抽象, 改用 LangGraph 的 `StateGraph` (5 节点固定拓扑). 同日二次简化: 删除 prepare_session + finish_interview 两个节点, probe_instruction 直接塞 judge prompt 不做 LLM 转写, final report 交给现有 post_session 管线.

**架构**:
- 5 节点固定图: `ask → [judge_off | judge_standard | judge_deep] → advance | ask`, advance done=True 直达 END
- 提纲是数据 (`Outline.sections[].questions[]`). 题目字段 = `id / ask / goal / must_get / max_followups + 可选 probe_instruction`
- 3 模式 follow_up_mode (off / standard / deep) 是路由 key, 由 `route_after_ask` dispatch
- probe_instruction 是研究员手写自然语言, 直接注入 judge prompt verbatim (不 LLM 转写)
- final_report 不再由 graph 生成; 现有 post_session 管线读 InterviewSession.transcript 异步生成报告
- 文件分层借鉴 google-gemini/gemini-fullstack-langgraph-quickstart

**关键决定**:
- AGENTS.md Rule 4 重写: v3 = ≤ 1 LLM call/turn (judge), 0/session 外环. v1 仍是 2 calls/turn (decide + generate).
- AGENTS.md Rule 9 放宽: v3 不写 per-turn `SessionEvent`. LangGraph PostgresSaver 是运行时权威; 终态写 `InterviewSession.transcript`, 触发 post_session 管线.
- AGENTS.md Rule 12 守住: routing functions 全是纯 `state -> Literal[node_name]`. 没有 LLM 决定边.
- AGENTS.md Rule 13 更新: 路由 key 从 `version: "v2"` 改为 `version: "v3"`. v1 sessions 走 `stream_turn` 不变.
- DeepSeek + LangChain 必须用 `with_structured_output(method="json_mode")`; 默认 `json_schema` 报 HTTP 400. Prompt 必须含 "JSON" 字样过 DeepSeek 安全检查. 锁在 `llm.py + prompts.py` 注释里.

**代码量**:
- 新增 `merism/conductor_v3/` (12 模块, ~1200 LOC + ~1500 行测试)
- 新增 `merism/voice/processors/moderator_v3.py` (190 行 pipecat FrameProcessor with 60s IdleTimer)
- 删除 `merism/conductor_v2/` (~3000 LOC + 150 tests). 净减 ~1800 LOC.
- migration 0038 加 `InterviewSession.follow_up_mode` 字段 (off/standard/deep, default standard)

**测试**:
- 142 tests pass (含 1 live smoke 真实 DeepSeek 跑 5 题 outline standard 模式 14.98s, 比 7-node 版本快 ~5s)
- ruff / ruff format / pyright pure-logic 全绿
- 前端 TypeScript 类型与 lint 仍绿; OutlineTab v2 高级面板已删除, v3 UI 编辑器待 R29 补

**文档**:
- ADR 0012 写定 + ADR 0009/0011 标 superseded
- `docs/specs/conductor-v3/` (requirements / design / tasks) 三件套, 已同步 5 节点设计
- AGENTS.md Rule 4/9/12/13 + "Engine architecture (Conductor v3)" 段全部按新架构重写

**剩余 (R29+)**:
- 前端 V3 outline 编辑器 (5 字段表单 + 3 状态 follow_up_mode radio)
- 真实参与者 dogfood 至少 1 场
- 视情况, 把 v3 checkpoint 表 schema 加 v1 SessionEvent 镜像 sink (如果分析需要)

**生产持久化** (2026-05-23 完成):
- `text_adapter.get_graph()` 用 `PostgresSaver` 替代 `InMemorySaver`
- 4 张 LangGraph 表已创建: `checkpoints / checkpoint_blobs / checkpoint_writes / checkpoint_migrations`
- 共享 `psycopg_pool.ConnectionPool` (min=1 max=10) 跨 daphne / gunicorn worker
- `saver.setup()` 幂等, 进程首次 build_graph 时自动调用
- 进程重启 + 多 worker 状态共享均已验证 (端到端 3 turn 测试通过, DB 写入 6 个 checkpoint 行)

**剩余 (R29+)**:
- 前端 V3 outline 编辑器 (5 字段表单 + 3 状态 follow_up_mode radio)
- 真实参与者 dogfood 至少 1 场
- 视情况, 把 v3 checkpoint 表 schema 加 v1 SessionEvent 镜像 sink (如果分析需要)

**生产持久化** (2026-05-23 完成):
- `text_adapter.get_graph()` 用 `PostgresSaver` 替代 `InMemorySaver`
- 4 张 LangGraph 表已创建: `checkpoints / checkpoint_blobs / checkpoint_writes / checkpoint_migrations`
- 共享 `psycopg_pool.ConnectionPool` (min=1 max=10) 跨 daphne / gunicorn worker
- `saver.setup()` 幂等, 进程首次 build_graph 时自动调用
- 进程重启 + 多 worker 状态共享均已验证 (端到端 3 turn 测试通过, DB 写入 6 个 checkpoint 行)

---

## ✅ R29 — Conductor v1 retirement (2026-05-23)

ADR 0013 落地. v3 验证全过 (142 单测 + live LLM smoke + 3 轮压力 + 真 DashScope STT/TTS 端到端 + post_session 兼容验证) → 删 v1.

**删的代码** (~5000 LOC + ~2000 LOC 测试):
- `merism/conductor/`: 14 个 v1 引擎文件 (moderator/decision_*/generation_prompt/guide_cursor/probe_blocks/adaptive_probing/concept_plan/state/prompts/moderator_eval/event_log/closure/text_chunker)
- `merism/voice/`: processors/moderator.py + interview_pipeline.py + services/moderator_processor.py
- 9 个 v1 单测 (test_closure/concept_plan/decision_validator/dynamic_probe/event_log/generation_prompt/moderator_eval/moderator_events/rule_clean/text_chunker)
- 2 个 management commands: evaluate_moderator + migrate_probe_blocks
- v1 voice consumer 测试 + truncation flow 测试

**保留为 cross-engine 工具** (`merism/conductor/`):
- post_session.py / transcript_helpers.py / llm_polish.py / rule_clean.py / signals.py / study_closure_signal.py / inbox_signals.py / tasks.py
- `__init__.py` 改成简洁 facade (无 v1 export)

**简化 routing**:
- `api/interview_message_view.py` 删 is_v3_session 分支 → 全部走 run_v3_turn
- `realtime/voice.py` 删 is_v3 分发 → guide_id 有则 ModeratorV3Processor, 无则 ad-hoc LLMProcessor
- `conductor_v3/router.py` 保留 is_v3_session 给 legacy 数据防御性读取, 不再用于请求路径

**数据迁移**:
- `python manage.py migrate_guide_to_v3 --all-studies --apply` 跑过, 23/23 v1 guides 全部转 v3
- 字段映射: v1.text → v3.ask, v1.probe_policy(none/light/standard/deep) → v3.follow_up_mode(off/standard/standard/deep), v1.probe_directions → v3.probe_instruction
- 丢: followup_depth, max_probes, required, intent, linked_stimulus_ids, type, scope, concept_block_id

**AGENTS.md**:
- Rule 4 重写: single-engine v3, ≤1 LLM call/turn, 0/session 外环
- Rule 13 重写: single-engine v3, 无 dual-engine routing, 无 cross-engine import concern
- Rule 9, 12 不变 (v3 exception 已在 ADR 0012 写定)

**测试结果**:
- 270 passed, 2 skipped (test_full_chain_invite_to_inbox 标 v1-only, R29 待 v3 重写), 2 pre-existing baseline failures (test_stt_processor_commits_turn_on_explicit_stop, test_django_settings_is_merism_test)
- ruff / ruff format / pyright 全绿
- `pre-v1-removal-2026-05-23` git tag 保存了删除前的 snapshot

**当前状态**:
- 单引擎 v3 (LangGraph 5 节点)
- 23 个 active study, 全部 v3 outline
- post_session 管线兼容 v3 transcript shape (v1-compat 转换在 finalize_to_session 完成)
- 真实 DashScope STT/TTS roundtrip 通过 (TTS 3.0s + STT 2.2s + graph 推进 = 完整闭环)

---

## ⏳ 进行中

### Codebook 治理 UI
- 后端完成（R16）
- ⬜ 前端：CodebookVersion 历史 + CodeChange 审批 + diff view
- ⬜ Admin：Codebook* 模型浏览界面

### Concept Testing 报告可视化
- 后端 `ConceptBlockViewSet.report` 已能返回 dimensions
- ⬜ Insights 页 / Report tab 接入概念维度可视化
- ⬜ 概念偏好 vs 人群（CohortSegment）交叉对比

### Conductor v2 dogfood + v1 退役
- ⬜ P3.5 v2 端到端 dogfood（3 场内部访谈，混合 voice / text）
- ⬜ P4.2 staging `migrate_guide_to_v2 --all-studies --apply` 灰度
- ⬜ P4.3 6 周 grace 期监控（v1 vs v2 错误率 / 首字延迟 p95 dashboard）
- ⬜ P4.4 ADR 0010 v1 退役（删 `merism/conductor/decision_prompt.py / decision_validator.py / moderator.py / guide_cursor.py / probe_blocks.py / adaptive_probing.py`）
- ⬜ P4.5 文档归档（`AGENTS.md` Rule 4 改"extract → generate"; `docs/PRODUCT.md` §5.2 同步; `docs/MIGRATION.md` 标 v2 完成）

### AGENTS.md / spec 同步
- ✅ AGENTS.md 规则 4 已更新为"决策 + 生成两节点"（2026-05-20）
- ✅ `docs/specs/merism-platform/requirements.md` Req 14 已同步（2026-05-20）
- ✅ `docs/specs/merism-platform/design.md` runtime model 段已同步（2026-05-20）
- ✅ `merism/conductor/{__init__,state,prompts,README}.{py,md}` 模块 docstring 已同步（2026-05-20）
- ✅ README.md / frontend/README.md / ADR 0002 / ADR 0006 已同步（2026-05-20）

### LLM observability
- ✅ Langfuse 自动注入（无 key 时 noop）
- ⬜ 接入 langsmith / helicone 之一作为 prod 替代
- ⬜ trace 关联到 SessionEvent / Conversation 行

### Email 渠道扩展
- ✅ SMTP / MCP 双形态
- ⬜ MCP 端 Resend 适配
- ⬜ 邮件打开率回报（list-unsubscribe 处理）

---

## 🔭 后续候选（post-current sprint）

- **i18n 完整链路** —— `InterviewSession.locale` 字段已就位，但 prompt + UI 仍是单语言
- **Stimuli S3 上传 UX** —— 当前需要 admin 后台上传，前端待做
- **共享报告权限管控** —— `CustomReport.is_public + share_token` 已能公开，缺 rate-limit / audit / revoke
- **跨 study Knowledge Explore 重排** —— 当前 RRF 简单融合，按 goal 相似度重排尚未上线
- **Theme confirmation UI** —— `Theme.status=draft` 已有，缺前端审批
- **SMS 渠道** —— 推到非 MVP
- **iOS / 微信小程序受访端** —— 推到非 MVP
- **Dark mode** —— tokens 已有 `semanticDark`，UI 未深度调过

---

## 历史归档

R14 / R15 完整 commit-by-commit 记录见 `docs/.archive_2026-05-20/ROADMAP.md`（备份在仓库内）。本 ROADMAP 把那些细节折叠进了上面的小节，重点放在"现在能做什么 / 还没做什么"。

---

> 修订记录
>
> - **2026-05-20** 全面同步当前代码状态。新增 R17-R26 段（Cleaning / ServiceSettings / ChannelTarget / Email / LinkTracking / Insights / Custom Reports / Themes / 2-node Conductor / pipecat Voice / Ask Merism / 受访者模式扩展）。明确"进行中"清单，把 R14/R15 的 commit 详细记录归档到 `.archive_2026-05-20/`。
> - **2026-05-11** R15 收尾。
> - **2026-05-10** R14 收尾。
