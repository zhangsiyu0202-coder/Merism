# Merism — 产品规范

> **单一事实源**。**2026-05-20 修订** —— 根据 `merism-app/` 当前代码状态全面同步，取代了之前 2026-05-09 reset 版本中已经过时的设计描述。
> 所有设计决策、API 约定、UI 规范在这里收敛。其他规划类文档（ROADMAP / RUNTIME / MIGRATION / ADR）跟本文不一致时以本文为准。
> 修改本文件必须在 PR 描述说明"跟原文哪里不一样、为什么改"；设计讨论先更新本文件，再动代码。

## 文档导航

| § | 内容 |
|---|---|
| [§0](#0-产品一句话定义) | 产品一句话定义 |
| [§1](#1-北极星research-goal-贯穿全程) | 北极星：Research Goal 贯穿全程 |
| [§2](#2-用户流程) | 用户流程（研究者 / 受访者） |
| [§3](#3-界面规范) | 界面规范（Scenes / Study tabs / 受访者房间 / 分析页 / Ask Merism） |
| [§4](#4-数据模型) | 数据模型（56 张表概览） |
| [§5](#5-ai-agent-架构) | AI Agent 架构（提纲审查 / 访谈主持 / 分析 / Ask Merism） |
| [§6](#6-外部服务栈) | 外部服务栈 |
| [§7](#7-端到端运行时) | 端到端运行时（事件溯源 / trace_id / 闭包 / Inbox） |
| [§8](#8-非目标不要扩张进来) | 非目标（不要扩张） |
| [§9](#9-开放问题) | 开放问题 |

---

## 0. 产品一句话定义

**Merism 是一个 AI 驱动的用户研究平台**：研究者写一个研究目标 → AI 帮他拟访谈提纲并审查修改 → 通过 CowAgent IM 渠道（飞书 / 企微 / QQ）或邮件群发或公开链接招募受访者 → 受访者进入房间与 AI 主持人进行语音 / 视频 / 文字访谈 → AI 在每场结束后自动清洗、抽取引用、归纳代码、生成个体洞察 → 跨多场综合出 Themes / Coverage / Insights / 自定义问答报告 → 多个研究沉淀成跨库问答知识库（Ask Merism）。

---

## 1. 北极星：Research Goal 贯穿全程

`Study.research_goal: TextField` 是唯一的"核心"。它是单字段、单值——**不允许**升级成多 goal flat list。创建 study 的第一步就让用户输入 research goal（例："调研 18–25 岁用户对 XX 零食的口味满意度"），此后的每个 AI 环节都以它为锚点：

| 环节 | research_goal 如何参与 |
|---|---|
| 提纲生成 | AI 按 goal 生成问题 sections |
| 提纲审查 | AI 检查每个问题是否服务 goal |
| 访谈主持 | AI 系统 prompt 注入 goal，避免跑题 |
| 个体分析 | AI 按 goal 抽取 highlights + tag 维度 |
| 群体综合（Themes） | 跨 session 聚类的语义中心仍以 goal 为约束 |
| Coverage | 计算每个 P0/P1/P2 goal 的覆盖度 |
| Insights | exec_summary / findings 全部以 goal 为锚 |
| Custom Report | 用户提问时，AI 先匹配 goal context |
| Ask Merism | 跨 study 检索时按 goal 相似度排序 |

**对话维度（tag）由 AI 自动推导**，不做独立 UI 配置：tag schema 来自 `research_goal + outline_questions`，研究者只需写好 goal 和提纲。

`Study.research_objectives: JSONField(default=list)` 是面向 UI 的"研究问题"有序列表（Settings tab 的 OrderedList 编辑），它是 `research_goal` 的辅助说明，不是替代——AI 仍以 `research_goal` 单字段为系统 prompt 锚点。

`StudyGoal` 是后续 R16 引入的可结构化 goal 模型（含 `priority: P0/P1/P2`、`coverage: float`、`is_answered: bool`），用于驱动 coverage 报告 + 决策 LLM 的"哪个 goal 还没答透"信号。它**不取代** `research_goal`，是覆盖度分析的计算单元。

---

## 2. 用户流程

### 2.1 研究者流程

```
[1] 创建 study
      · 唯一必填：research_goal（一句话）
      · 可选：研究背景 / 假设 / 成功指标
      · 默认 interview_mode = voice，可改 video / text / offline
      ↓
[2] Brief tab：写背景 / 假设 / 成功指标 + dashboard 看进度
      ↓
[3] Outline tab：编辑提纲
      · AI 基于 goal 生成初稿
      · 可拖拽排序 / 编辑 / 增删问题
      · 每题单独配置：probe_policy（none/light/deep）+ max_probes
        + probe_blocks（动态探针，可选触发条件）+ 是否必答
        + linked_stimulus_ids
      · 顶部 [✨ 让 AI 审查] → 右侧 chat 抽屉
      ↓
[4] Screener tab：筛选条件编辑（自然语言 + AI 转结构化）
      ↓
[5] Stimuli tab：刺激物 / 概念测试管理
      · 普通 stimulus（jpg/png/mp4/pdf/text/link）
      · ConceptBlock：N 个 Concept 同台对比，rotation 三选一
        （fixed / random_per_session / latin_square）
      ↓
[6] Recruit tab：渠道 + 链接 + 群发
      · StudyLink 自动生成（slug 短链 + 可选 short_link_domain）
      · ChannelConfig：飞书 / 企微 / WeCom Bot / QQ Group / QQ Guild / Email
      · MessageTemplate + RecruitmentBroadcast + DeliveryRecord
      · 可选 require_invitation：单次令牌（Invitation 表）+ PIPL 合规
      ↓
[7] 自测：以受访者身份打开 /i/<slug>/?preview=1
      · 不创建真实 Participation
      · 不写入 Session
      · 不扣配额
      · 右下角"自测模式"角标
      ↓
[8] 正式开始：Live 状态
      · Sessions tab dashboard 看每场进度
      · Inbox 收到 session_completed / insight_ready / study_completed
        通知（unique_together 去重）
      ↓
[9] 分析：3 个 tab 协同
      · Report tab：StudyReport 4 panel（exec_summary / quant_panel /
        qual_panel / insight_nuggets）+ 一次性快照
      · Insights 页（auto-generated）：StudyInsights / Highlights /
        Findings 三层结构，含 chart_spec / themes / supporting_evidence
      · Custom Reports 页（user-created）：CustomReport / ReportSegment
        / ReportQuestion，每题独立 AI 分析 + 可对比 segment + 公开
        share_token
      · Analysis tab：Themes（HDBSCAN 聚类）+ CoverageSnapshot（按
        StudyGoal 优先级加权）+ CohortSegment 比对
      ↓
[10] 沉淀：自动写入跨库知识库
      · KnowledgeChunk（pgvector）+ BM25
      · Ask Merism /ask 跨 study 自然语言问答
```

### 2.2 受访者流程

```
[1] 打开邀请链接 /i/:slug
      · 可选 ?t=<token>（StudyLink.require_invitation=True 时必带）
      · 可选 ?preview=1&token=xxx（自测模式）
      · 可选 ?mode=text（强制文字模式，由 ParticipantEntryPage 注入）
      ↓
[2] resolve_link：检查 link.is_active / expires / study.status
      · auto-close 感知：study_full(409) vs link_closed(410)
      · 若 require_invitation=True，校验 token
      · 创建或重用 Participation（cookie + browser_token 续接）
      · trace_id 从 Invitation 继承
      ↓
[3] Consent 页：告知 AI 主持 + 录音/录像同意 + 隐私条款
      ↓
[4] Screener 快速筛（可选 1–3 道）
      · 不符合 → 感谢退出
      · 符合 → 通过；screener_score 写入 Participation
      ↓
[5] 准备页 / 模式选择
      · voice：仅麦克风
      · video：摄像头 + 麦克风
      · text：键盘对话（无 STT/TTS，SSE 流回 AI 回复）
      · offline：研究者手动录入
      ↓
[6] InterviewRoom（voice / video）或 TextInterviewPage（text）
      · 单一 stream_turn 入口贯穿三种模式
      · 每个 user turn → conductor 2-node pipeline（决策 + 流式生成）
      · WebSocket 语音管道：STT → Moderator → TTS → ConversationState
      · 支持 PTT barge-in（study.barge_in_enabled，默认 off）
      · 6 信号闭包检测：close / all_p0 / leaving_intent / idle / ws_disconnect / max_duration
      ↓
[7] 完成访谈
      · session.status = COMPLETED → Participation.status = COMPLETED
      · 触发 SessionEvent(kind=session_lifecycle, payload={ended})
      · post_save signal → process_completed_session Celery 任务
      · 感谢页 + 可选反馈
```

---

## 3. 界面规范

### 3.1 顶层 Scenes（前端 14 个）

```
Scene.Home              /                       — 5 列 KPI + Studies 横排 + 第一研究 hero
Scene.Studies           /                       — 同 /，filter tabs（All/Active/Drafts/Archived）
Scene.Ask               /ask                    — Ask Merism（跨 study 问答）
Scene.Inbox             /inbox                  — 研究者通知（InboxItem 列表）
Scene.Repository        /repository             — 知识库浏览
Scene.Assistant         /assistant              — AI assistant
Scene.Settings          /settings  /settings/:section
Scene.Study             /studies/:id/:tab       — 9 个 sub-tab（见 §3.2）
Scene.Insights          /insights?study=...     — auto-generated 综合洞察
Scene.Reports           /reports?study=...      — user-created custom reports 列表
Scene.Reports (detail)  /reports/:reportId      — 单个 CustomReport 详情
Scene.InterviewRoom     /interview/:sessionId   — 受访者音视频房间
Scene.SessionTranscript /sessions/:id/transcript — 单场转写阅读
Scene.ParticipantEntry  /i/:slug                — 受访者入口（consent / screener / mode）
Scene.Login             /login
Scene.Welcome           /welcome                — 营销落地页
Scene.Error404          /404
```

### 3.2 Study 详情 tabs（9 个）

```
Brief  |  Outline  |  Screener  |  Stimuli  |  Recruit  |  Sessions  |  Report  |  Analysis  |  Settings
```

| Tab | 内容 |
|---|---|
| **Brief** | 研究目标 / 背景 / 假设 / dashboard（进度、完成率）|
| **Outline** | 提纲编辑器 + AI 审查抽屉 + probe_blocks 配置 |
| **Screener** | 筛选条件编辑（自然语言 + AI 转结构化）|
| **Stimuli** | 单 stimulus + ConceptBlock 概念测试管理 |
| **Recruit** | 链接生成 + ChannelConfig + Broadcast + Delivery 状态监控 |
| **Sessions** | 已完成 session 列表 + 跳转 transcript |
| **Report** | StudyReport 4 panel 快照（exec_summary / quant / qual / nuggets）|
| **Analysis** | Themes + CoverageSnapshot + CohortSegment + Custom Report 入口 |
| **Settings** | research_objectives 编辑 + interview_mode + barge_in + 配额 / 删除 / 导出 |

### 3.3 提纲编辑器 + AI 审查

主区可编辑 + 顶部 `[✨ 让 AI 审查]` 按钮。点击 → 右侧抽屉打开 chat。

每个 question 卡片含：
- text（问题文本）
- probe_policy（none / light / deep）
- max_probes（0..5，整数）
- probe_blocks（动态探针：dict 列表 `[{id, type, prompt, trigger, condition, max_rounds, priority}]`，研究者可手动配多条触发条件）
- required（是否必答）
- linked_stimulus_ids
- followup_depth（兼容字段，等价 max_probes）

AI 审查（function calling 形式，单次往返）：
```json
{
  "reply_markdown": "我看了下提纲，有 3 个建议……",
  "proposed_changes": [
    {"op": "modify_question", "question_id": "q3", "new_text": "..."},
    {"op": "insert_question", "after_id": "q5", "question": {...}},
    {"op": "remove_question", "question_id": "q7"}
  ],
  "awaiting_user_decision": true
}
```
研究者点 `[应用修改]` → 前端逐条 apply。

### 3.4 Stimuli 与 Concept Testing 2.0

**普通 Stimulus**：jpg/png/gif · mp4/webm · pdf · 文字 · 外链。提纲题可关联 1+ stimulus_id；访谈时左 2/3 区覆盖展示。

**ConceptBlock + Concept**（同台对比）：

```
ConceptBlock(title="Snack 包装 A/B/C", rotation=latin_square)
├── Concept(label="Concept A", rank=0, stimulus=img-001, notes="环保牛皮纸")
├── Concept(label="Concept B", rank=1, stimulus=img-002, notes="撞色塑料")
└── Concept(label="Concept C", rank=2, stimulus=img-003, notes="磨砂铝箔")
```

- 三种 rotation 策略：
  - `fixed` —— 严格按 rank
  - `random_per_session` —— 每场随机
  - `latin_square` —— `ConceptRotationCursor.position` 原子 +1，跨 session 一阶平衡（每个 concept 在每个位置出现 N/|concepts| 次）
- 受访者看到的是数字 chip（"Concept 1 of 3"），label 仅内部 / AI prompt / 报告可见
- 切换瞬间，pipeline 推 `StimulusShowFrame` → 前端 crossfade 切图
- 报告维度（`merism/concept/dimensions.py`）：sentiment / purchase_intent / appeal / comprehension，tiebreak `purchase_intent → appeal → sentiment → sessions_seen`

### 3.5 受访者房间（InterviewRoom）

布局（左 2/3 / 右 1/3）：

```
┌─ 顶部 Logo ───────────────────────────────────────────────┐
├──────────────────────────────────────────────┬────────────┤
│ 左 2/3 — AI 区                                │ 右 1/3 —    │
│  · AI INTERVIEWER 标签                         │ 对话栏      │
│  · 当前问题文本（大字）                        │ · 实时字幕  │
│  · ● Begin response（紫色 PTT 按钮）           │ · AI 回复   │
│  · 预览区（音频：占位+波形 / 视频：摄像头 /    │ · 附件上传  │
│    刺激物覆盖 / 概念图 crossfade）              │ · 文字输入  │
└──────────────────────────────────────────────┴────────────┘
```

**模式差异**：

| 维度 | voice | video | text | offline |
|---|---|---|---|---|
| STT | Qwen Paraformer 流式 | 同 voice | — | — |
| TTS | Qwen CosyVoice 流式 | 同 voice | — | — |
| Vision | — | Qwen-VL-Max（每 10s 抽帧） | — | — |
| 录制 | 仅麦音频 → S3 | 音频 + 视频分轨 → S3 | — | — |
| 对话入口 | WebSocket /ws/sessions/<id>/voice | 同 voice | SSE POST /api/sessions/<id>/message/ | 研究者手录 |
| barge-in | study.barge_in_enabled 控制（默认 off）| 同 voice | — | — |
| 完成率（推算） | 高 | 中（摄像头摩擦） | 高 | — |
| 成本/场（推算） | ~$2–3 | ~$5–8 | ~$0.5 | — |

**自测模式** `?preview=1&token=xxx`：
- 不创建真实 Participation
- 不写入 Session
- 不扣配额
- 右下角橙色"自测模式"角标

### 3.6 分析页（Insights vs Custom Reports）

`StudyReport` / `Insights` / `CustomReport` 是三层互补结构：

| 层 | 模型 | 触发 | 用途 |
|---|---|---|---|
| **Report** | `StudyReport` | `Study.report` 一次性快照 | 4-panel 总览：exec_summary / quant / qual / insight_nuggets，给研究者扫一眼用 |
| **Insights** | `StudyInsights` + `InsightHighlight`（3-6 条核心要点）+ `InsightFinding`（深度发现含 chart / themes / nuggets）| Celery 后台自动生成 | 系统标准化深度洞察，写完即可分享 |
| **Custom Reports** | `CustomReport`（含 share_token / is_public）+ `ReportSegment`（人群子集）+ `ReportQuestion`（每题独立 AI 分析）| 用户主动新建 + 提问 | 用户驱动的探索：分人群对比 / 自定义问题 / 公开分享链接 |

**Insights 页布局**：

```
[Hero] Executive Summary（含 completed_interviews / avg_session_minutes / topics）
[Highlights] 3-6 张要点卡（headline + summary + 可选跳转 Finding）
[Findings] 可展开 accordion
  · chart_spec（柱/线/饼）
  · chart_interpretation（图表解读）
  · themes / subthemes
  · insight_nuggets
  · supporting_evidence（quote 引用）
```

**Custom Report 页布局**：

```
[标题 + 状态 + 公开 share_url]
[AI Synthesis] 跨问题综合解读
[Segments] 横向人群对比条（如 "power_users vs new_users"）
[Question 1]
  · ai_summary
  · chart_spec（可选）
  · themes
  · quotes（含 session 跳转）
[Question 2] ...
```

ChartRenderer 用 Chart.js 风格；citation 可点击跳转到 `/sessions/:id/transcript#ts=N`。

### 3.7 Ask Merism（跨 study 问答）

`/ask` 是顶层 Scene。流程：

1. 用户提问 → `POST /api/ask/stream/`（SSE）
2. 后端：
   - retriever（KnowledgeChunk pgvector + BM25 + RRF k=60）
   - generator（function calling）→ 流式 markdown + tool_call
3. AI 可调用的工具：
   - `aggregate_tag(tag_name)` → 该 tag 的分布（画图用）
   - `filter_sessions(criteria)` → session_ids 列表
   - `cite_quote(session_id, ts)` → 原文片段
4. 输出落到 `Conversation.messages`（直接持久化在 JSONField）+ 可选 `AskArtifact`（typed renderable block：research_quote / comparison_table / theme_map / insight_card / study_summary）
5. 公开分享：`CustomReport.share_url` `/shared/report/<token>/` 或 AskArtifact 可独立暴露 `short_id` URL

**Conversation 自动起标题**：`merism/memai/title_generator.py` 在第一轮 user turn 后异步生成。

---

## 4. 数据模型

**56 张表**（Django app registry 实数）。每张表都遵循 `merism_<noun>` 表名前缀（`AGENTS.md` 规则 2）+ `team_id` 多租户隔离（规则 3）。

> 所有模型定义在 `merism/models/`（除 codebook 治理在 `merism/codebook/models.py`）。完整字段以 `merism/migrations/0001_initial.py` 起的 32 个迁移为准。

### 4.1 团队 / 用户

| 模型 | 说明 |
|---|---|
| `Organization` | 组织 |
| `OrganizationMembership` | 组织 ↔ 用户成员关系 |
| `Team` | 工作区（多租户隔离边界）|

### 4.2 Study 域

| 模型 | 说明 |
|---|---|
| `Study` | 核心研究单元，`research_goal: TextField` 单字段；status ∈ `{draft, live, closed}`（已从 6 状态简化）；`interview_mode ∈ {voice, video, text, offline}`；`barge_in_enabled`、`codebook(JSONField)`、`recruitment_quotas`、`target_audience`、`target_completed_count`、`research_objectives(list)` |
| `StudyLink` | 公开链接，`slug` 短链；`link_mode ∈ {anonymous, named}`；`require_invitation`；`short_link_domain`；`clicks` 计数 |
| `StudyTemplate` | 创建向导种子模板（system 内置 + team 自建）|
| `StudyTrigger` | 行为触发招募规则（在 Celery beat 跑）|

### 4.3 提纲 / 筛选 / 刺激物

| 模型 | 说明 |
|---|---|
| `InterviewGuide` | `version`、`is_current`、`sections(JSONField)`；section.questions 含 `probe_blocks`（动态探针）|
| `Screener` | `questions(JSONField)`、`pass_logic` |
| `Stimulus` | `kind ∈ {image, video, text, pdf, link}`、`content`、`linked_question_ids` |

### 4.4 Concept Testing 2.0

| 模型 | 说明 |
|---|---|
| `ConceptBlock` | 同台对比组，`rotation ∈ {fixed, random_per_session, latin_square}` |
| `Concept` | 单 concept 变体，绑定一个 `Stimulus`，含 `label`（内部）+ `rank`（基线序）|
| `ConceptRotationCursor` | latin_square 跨 session 平衡的持久化游标，`F("position")+1` 原子推进 |

### 4.5 受访者 / Session

| 模型 | 说明 |
|---|---|
| `Participant` | 跨研究的人；只存最少 PII（external_id / email / name / attributes）|
| `Participation` | 一次受访尝试；`status ∈ {invited, started, consented, screened, interviewing, completed, dropped}`；`is_preview`、`browser_token`、`trace_id`、`consented_at`、`completed_at`、`screener_score`、`delivery_id` |
| `InterviewSession` | 一场访谈；`mode ∈ {voice, video, text, offline}`；`status ∈ {pending, active, completed, failed}`；`transcript`、`moderator_state`、`decision_log`、`vision_frames`、`audio_s3_key`、`video_s3_key`、`trace_id` |
| `InterviewRecording` | 视频录像元数据（独立表，可独立删除）|
| `SessionEvent` | **append-only 事件日志**（R15）；`kind ∈ {user_turn, model_reply, decision, state_transition, interruption, error, session_lifecycle}`；`(session, seq)` 唯一约束；权威源，`moderator_state` 是 cache |
| `SessionQuote` | 高价值引用，`text`、`turn_indices`、`question_id`、`concept_id`、`tags`（含 deductive / inductive_suggestions / sentiment / action_type）、`importance` |
| `Invitation` | 单次令牌（PIPL/GDPR 闭合受众），绑定 StudyLink；`recipient_hash`、`token`、`status ∈ {pending, delivered, accepted, expired, revoked}`、`trace_id` |

### 4.6 招募 / 渠道

| 模型 | 说明 |
|---|---|
| `ChannelConfig` | 团队 IM 凭证（Fernet 加密）；`channel_type ∈ {feishu, wecom, wecom_bot, qq_group, qq_guild, email}` |
| `ChannelTarget` | 群发目标（独立于 ChannelConfig，支持 group / user 两种 recipient_kind）|
| `MessageTemplate` | 邀请模板，`{{study_link}}` 等占位符；system 内置 + team 自建 |
| `RecruitmentBroadcast` | 一次群发任务；`status ∈ {draft, approved, sending, completed, partially_failed, failed}`；`approved_snapshot`（审批时的内容快照）|
| `DeliveryRecord` | 单次投递结果，`recipient_id`、`status ∈ {pending, sent, delivered, failed}`、`message_id`、`trace_id` |
| `ChannelHealthCheck` | 30 分钟探活日志（append-only）|

### 4.7 知识库 / RAG

| 模型 | 说明 |
|---|---|
| `TeamResearchKnowledgeBase` | L1 团队级 KB |
| `StudyKnowledgeBase` | L2 单 study KB |
| `KnowledgeDocument` | RAG 文档实体 |
| `KnowledgeChunk` | embedding chunk（`pgvector.VectorField` 1536 维 + sqlite JSONField fallback）|
| `Glossary` | ASR 修正词表（canonical + variants），团队级 / 单 study 级 |

### 4.8 报告 / Insights / Custom Reports（三套并存）

**报告快照**（一次性 4-panel）：

| 模型 | 说明 |
|---|---|
| `StudyReport` | `content`（exec_summary / quant_panel / qual_panel / insight_nuggets）+ `charts`（Pydantic 验证：`merism/reports/schema.py`）|
| `AggregateSynthesis` | 兼容老的群体综合输出（保留向后兼容）|
| `CustomReportQuery` | 老 sidebar 提问的兼容表（保留）|
| `SessionInsight` | 个体洞察：`summary`、`highlights`、`tags`、`extracted_tasks`、`trace_id` |

**Insights**（auto-generated 三层）：

| 模型 | 说明 |
|---|---|
| `StudyInsights` | study 容器；`status ∈ {pending, generating, ready, failed}`；`completed_interviews`、`avg_session_minutes`、`interview_topics`、`executive_summary` |
| `InsightHighlight` | 3-6 张高层要点卡；`headline`、`summary`、`icon`、可选 `linked_finding` |
| `InsightFinding` | 深度发现 accordion 行；`chart_spec`、`chart_interpretation`、`themes`、`subthemes`、`insight_nuggets`、`supporting_evidence` |

**Custom Reports**（user-created）：

| 模型 | 说明 |
|---|---|
| `CustomReport` | `title`、`status`、`ai_synthesis`、`share_token`、`is_public` |
| `ReportSegment` | 人群子集（`selector` 跟 CohortSegment 同形）|
| `ReportQuestion` | 单问题独立 AI 分析；`question_type ∈ {open_ended, multi_select, single_select, rating, ranking}`；`ai_summary`、`chart_spec`、`themes`、`quotes`；可绑定 `segment` 做对比 |

### 4.9 跨 session 分析

| 模型 | 说明 |
|---|---|
| `StudyGoal` | 结构化研究问题，`priority ∈ {P0, P1, P2}`、`coverage`、`is_answered`（驱动 coverage 报告）|
| `Theme` | 跨 session 引用聚类（HDBSCAN）；含 `centroid_embedding` (pgvector) 用于增量分配；`status ∈ {draft, confirmed, archived}` |
| `CoverageSnapshot` | 每场结束后重建；`goal_coverage(dict)`、`overall_coverage`（按优先级加权）、`gaps`、`recommendations` |
| `CohortSegment` | 团队定义的人群子集（如 "power_users" / "new_users"），用于 theme 分布对比 |

### 4.10 Codebook 治理（R16，已完成）

| 模型 | 说明 |
|---|---|
| `CodebookVersion` | 不可变快照；`(study, version)` 唯一；`codes` 全量 JSON |
| `CodeChange` | 单次变更提议；`change_type ∈ {add, merge, split, rename, deprecate}`；`status ∈ {proposed, approved, rejected, applied}` |
| `CodeMapping` | old_code_id → new_code_id 映射，给 RetaggingJob 做 quote 重打标 |

### 4.11 通知 / 链接追踪

| 模型 | 说明 |
|---|---|
| `InboxItem` | 研究者通知；`kind ∈ {session_completed, insight_ready, study_completed, study_stuck}`；`unique_together=(team, kind, ref_kind, ref_id)` 数据库去重 |
| `LinkClick` | Dub.co 风格点击事件：`identity_hash` 去重、`utm_*`、`device_type`、`referer`、`referrer_participation`（链式追踪）|
| `LinkShareEvent` | 复制 / 分享 / 转发动作；用于上下游链路 |

### 4.12 Ask Merism / Memory

| 模型 | 说明 |
|---|---|
| `Conversation` | 对话线程；`messages(JSONField)` 直接持久化；可选 `study` 上下文 |
| `AgentMemory` | 语义可检索记忆（按 team + 可选 user）|
| `CoreMemory` | org/team/user 级常驻事实，永远进 prompt（< 500 token）|
| `AskArtifact` | AI 生成的结构化 block：`research_quote / comparison_table / theme_map / insight_card / study_summary`；`short_id` 可独立分享 |

### 4.13 服务配置

| 模型 | 说明 |
|---|---|
| `ServiceSettings` | 每团队 LLM/TTS/STT/Embedding 配置（base_url + model + 加密 api_key），优先级高于环境变量 |

### 4.14 已废弃 / 不再使用

旧 PRODUCT.md 提到的以下模型在当前代码里已经不再扮演原始角色：
- `StudyTransition`（状态机审计表）—— 已简化为直接改 `Study.status`，无独立审计表
- `Conductor.policies` 持久化（coverage_steer / engagement / off_topic）—— **policies 持久化已不存在**；coverage 信号通过 `CoverageSnapshot` + 决策 prompt 动态注入

---

## 5. AI Agent 架构

实际部署的 agent / runner（2026-05-20）：

| Agent | 位置 | 类型 | 触发 |
|---|---|---|---|
| **Outline Review** | `merism/memai/agents/outline_review.py` | 对话式（function calling）| 研究者 Outline tab 抽屉 |
| **Interview Moderator** | `merism/conductor/moderator.py` | **2-node 流式 pipeline** | 受访者 user turn |
| **Quote Extractor** | `merism/memai/agents/quote_extractor.py` | 批量 | post_session 第 3 步 |
| **Quote Tagger** | `merism/memai/agents/quote_tagger.py` | 批量 | post_session 第 4 步 |
| **Codebook Seeder** | `merism/memai/agents/codebook_seeder.py` | 一次性 | post_session 第 2 步（每 study idempotent）|
| **Inductive Code Suggester** | `merism/memai/agents/inductive_code_suggester.py` | 批量 | post_session 第 5 步（codebook 治理）|
| **Codebook Reviewer** | `merism/memai/agents/codebook_reviewer.py` | LLM 决策 | inductive 累计后审批 |
| **Session Insight Generator** | `merism/memai/agents/session_insight_generator.py` | 单场 | post_session 第 7 步 |
| **Theme Synthesizer** | `merism/analysis/themes/theme_summarizer.py` | 跨 session | saturation / target_reached 触发 |
| **Study Narrative Summary** | `merism/memai/agents/study_narrative_summary.py` | study 级 | StudyInsights 生成时 |
| **Recruitment Message** | `merism/memai/agents/recruitment_message.py` | 单次 | 研究者起草招募文案 |
| **Title Generator** | `merism/memai/title_generator.py` | 异步 | Conversation 第一轮后 |
| **Ask Merism Runner** | `merism/api/ask_views.py:ask_stream` | 流式 + tool calling | /ask SSE |
| **Custom Report Q&A** | `merism/memai/agents/analysis.py:answer_custom_report_question` | 单题 | 用户提问 |

### 5.1 Outline Review Agent

不变。详见 §3.3 输出 schema。

### 5.2 Interview Moderator —— 2-node 流式 pipeline

> ✅ **架构变更说明**：之前版本 PRODUCT.md / AGENTS.md 规则 4 / `merism-platform` Req 14 描述为"单 LLM 调用同时返回 (text, next_action)"。**当前代码已改为两次顺序 LLM 调用**：先非流式拿决策，再流式生成回复。AGENTS.md 规则 4 与 platform spec Req 14 已在 2026-05-20 同步到 2-node 描述。

**形态**：流式 voice + text + 视频，三种模式共享同一个 `stream_turn` 入口（`merism/conductor/moderator.py`）。

**单轮流程**：

```
participant message
  │
  ▼
resolve ExecutionState（含 guide cursor / coverage gap / concept context）
  │
  ▼
┌──────────────────────────────────────────┐
│ Node 1 — coverage_steer                  │
│ • 非流式 LLM call                         │
│ • 输出 ModeratorDecision（function call） │
│ • {next_action, next_question_id?,       │
│    target_goal_id?, probe_kind,           │
│    dynamic_trigger?, matches_rule}       │
│ • ~400-800ms                              │
└──────────────────────────────────────────┘
  │
  ▼
decision_validator —— 服务端硬规则
  │ Rule 1a: probe_policy=none → followup 强制 move_on
  │ Rule 1b: probe_policy=deep + probes_done=0 + move_on → 强制 followup
  │ Rule 2:  probes_done >= max_probes → 强制 move_on
  │ Rule 3:  无效 dynamic probe → 降级到 preset 或 move_on
  ▼
┌──────────────────────────────────────────┐
│ Node 2 — generate                        │
│ • 流式 LLM call                           │
│ • 逐 token yield 给 TTS / SSE             │
│ • ~300-500ms 首 token                     │
└──────────────────────────────────────────┘
  │
  ▼
post-stream persistence
  • _apply_decision_to_state（mark_answered / mark_followup_used / phase）
  • InterviewSession.moderator_state 更新（cache）
  • InterviewSession.transcript 追加 2 行
  • SessionEvent 追加 user_turn / model_reply / decision 三行（权威源）
  • Closure 检查（6 信号）—— 命中即 complete_session
```

**为什么从单调用改成 2-node**：

- PTT 模式给我们 ~1s 首 TTS 预算，跑得起一次决策调用
- 让"决策"成为一等结构化步骤，比把 tool_call 塞进流式输出更容易
- 决策模型可独立选型（Reasoner）、独立优化（temperature=0）
- 不引入 LangGraph：仍然是两个顺序 `await`，无图、无策略层

**仍然不做**（保留 spec Req 14.7 的克制）：

- ❌ macro / meso / micro 三层决策
- ❌ 独立 policy（coverage_steer / engagement / off_topic）的持久化
- ❌ 自带任意工具的 ReAct agent

### 5.3 Post-session 分析管道（Celery 链）

`session.status=COMPLETED` → `conductor.signals` → `process_completed_session(session_id)` → `process_session_transcripts`：

```
1. transcript polish（多阶段）
   · stage1_asr_correct（Glossary 替换）
   · stage3_normalize（NFKC + zh/en 混排）
   · rule_clean（filler 词正则）
   · llm_polish（批量 LLM）
   · stage6_semantic_merge（可选，LLM 成本，opt-in）
2. seed_codebook（每 study 一次，idempotent）
3. extract_quotes（→ SessionQuote 行）
4. tag_quotes（deductive + inductive_suggestions + sentiment）
5. promote_inductive_suggestions（高频 inductive → 进 codebook）
6. codebook governance pipeline
   · InductiveCodeSuggester → CodeChange(proposed)
   · CodebookReviewer → approve/reject
   · CodebookVersionManager → 新版本快照 + CodeMapping
   · RetaggingJob → 影响的 quote 重打标
   · saturation 检测 → 可能触发 ThemeSynthesizer
7. RAG indexing（quotes → KnowledgeChunk）
8. SessionInsight 生成（→ Inbox insight_ready）
9. cross-session analysis
   · rebuild_themes（HDBSCAN clusterer）
   · rebuild_coverage（按 P0/P1/P2 加权）
```

每一步都是幂等的、单独可重试的 Celery 任务。失败一步不影响前面已落库的结果。

### 5.4 Ask Merism

详见 §3.7。后端关键文件：
- `merism/api/ask_views.py` —— `ask_stream` SSE + `ask_title` 标题
- `merism/api/conversation_views.py` —— Conversation CRUD
- `merism/knowledge/search.py` —— pgvector + BM25 + RRF k=60 fusion
- `merism/memai/agents/study_narrative_summary.py` —— Study summary artifact

---

## 6. 外部服务栈

| 服务 | 用途 | 选型 | 实际接入位置 |
|---|---|---|---|
| **LLM** | 所有文本生成 / 推理 | DeepSeek v3 / DeepSeek Reasoner（OpenAI-compat）| `merism/memai/llm.py` + `merism/llm_gateway/client.py` |
| **TTS** | AI 语音输出 | Qwen CosyVoice（流式） | `merism/tts.py` + `merism/voice/services/qwen_tts.py` |
| **STT** | 受访者语音转写 | Qwen Paraformer-realtime | `merism/stt.py` + `merism/voice/services/qwen_stt.py` |
| **Vision** | 视频模式抽帧 + 用户上传图片 / 视频 | Qwen-VL-Max | `merism/vision.py` |
| **Embedding** | RAG 向量化 | DeepSeek embedding（带回退） | `merism/knowledge/embeddings.py` |
| **对象存储** | 录音 / 录像 / 刺激物 / 附件 | S3 / MinIO（直接用 boto3）| `OBJECT_STORAGE_*` 环境变量 |
| **IM 招募** | 飞书 / 企微 / WeCom Bot / QQ Group / QQ Guild | CowAgent adapters | `merism/recruitment/adapters/` |
| **Email 招募** | 邀请备用渠道（**已加入 MVP**）| SMTP / MCP-backed | `merism/recruitment/adapters/email_adapter.py` |

### 服务路由（每团队可改）

`merism/llm_gateway/client.py:get_client(logical_name, *, team, trace_id)` 是统一入口：

1. 优先读 `team.service_settings`（`ServiceSettings` 表）—— 团队可在 admin 自配 base_url + model + 加密 api_key
2. 回退 `MERISM_LLM_API_KEY` / `MERISM_LLM_BASE_URL` 环境变量

logical name 映射：

| logical_name | service_type |
|---|---|
| `chat` / `reasoner` / `vision` | llm |
| `embedding` | embedding |
| `asr_realtime` | stt |
| `tts_realtime` | tts |
| `omni_realtime` | llm |

### 不再使用 / 已替换

| 旧文档说 | 实际 | 原因 |
|---|---|---|
| "对象存储：PostHog object_storage" | boto3 直接对接 S3 / MinIO | merism-app 没有 PostHog 依赖 |
| "所有 LLM 调用通过 `posthoganalytics.ai.openai` 包装" | `openai.OpenAI`（DeepSeek base_url） + Langfuse 可选 | 同上 |
| "Email / SMS 非 MVP" | Email 已加入（SMTP/MCP），SMS 仍延后 | recruitment.adapters.email_adapter 落地 |

---

## 7. 端到端运行时

详见 [`RUNTIME.md`](RUNTIME.md)，本节是简要索引。

### 7.1 数据骨干

七张表用 `trace_id: UUIDField` 串联起一个受访者的完整旅程：

```
Invitation
   ↓ trace_id 透传
DeliveryRecord
   ↓
Participation（rehydrate via cookie OR invitation token）
   ↓
InterviewSession（trace_id 复制自 participation）
   ↓
SessionEvent（kind=user_turn / model_reply / decision / state_transition / interruption / error / session_lifecycle）
   ↓
SessionInsight
   ↓
InboxItem（research notification）
```

### 7.2 闭包（6 信号 OR + closing_grace）

| # | 信号 | 触发条件 |
|---|---|---|
| A | `close_decision` | LLM `next_action == "close"` 且不在 closing grace 内 |
| B | `closing_grace_exhausted` | phase=closing 且 closing_rounds_remaining ≤ 0 |
| C | `all_p0_answered` | 全部 P0 StudyGoal `is_answered=True` 且 elapsed ≥ `min_duration_minutes`（默认 5）|
| D | `leaving_intent` | 最后 user_turn 命中告别 regex（en + zh）|
| E | `idle_timeout` | 上一个 user_turn 距今 > 120s（且至少有 1 turn）|
| F | `ws_disconnect` | WebSocket 断开 ≥ 30s 且 turn 数 ≥ 4 |
| G | `max_duration` | elapsed ≥ `max_duration_minutes`（默认 45）|

加一个第 8 道安全网：Celery beat `abandon_stuck_sessions` 每 10 分钟扫一次，把 in-progress 超 2h 的 session 强制 COMPLETED。

`complete_session` 用 `select_for_update` 原子写：set session.status / participation.status 都为 COMPLETED + 写 `session_lifecycle=ended` 事件。

### 7.3 Study auto-close

`Participation.status=COMPLETED` 触发 `study_closure_signal`：

```python
with transaction.atomic():
    study = Study.objects.select_for_update().get(id=...)
    if study.actual_completed_count >= study.target_completed_count:
        study.status = CLOSED
        StudyLink.objects.filter(study=study, is_active=True).update(is_active=False)
```

`Study.actual_completed_count` 是 `@property`（`COUNT(*)`），不是 stored counter——避免 race-prone `+= 1`。

### 7.4 Inbox 通知

三个 `post_save` handler 写入 `InboxItem`：

| 信号 | InboxItem.kind |
|---|---|
| `InterviewSession.status=COMPLETED` | `session_completed` |
| `SessionInsight.__init__` | `insight_ready` |
| `Study.status=CLOSED` | `study_completed` |

`unique_together=(team, kind, ref_kind, ref_id)` 在 DB 级去重；重复信号自然 noop。

### 7.5 观测

- `merism/observability.py:bind_trace(trace_id=...)` —— structlog `contextvars` 块
- 管理后台 `/admin/merism/participation/<id>/trail/` —— 按 trace_id 聚合 DeliveryRecord + SessionEvent + SessionInsight 的时间线
- Prometheus `/metrics` —— `django_prometheus` 中间件
- Sentry 集成可选（`merism/sentry.py`）

---

## 8. 非目标（不要扩张进来）

| 不做 | 为什么 |
|---|---|
| ❌ Conductor macro/meso/micro 三层决策 | platform spec Req 14.7，2-node 已经够用 |
| ❌ 独立 policies 持久化（coverage_steer / engagement / off_topic）| spec Req 21.5，决策 prompt 动态注入 coverage 已能覆盖 |
| ❌ PostHog 平台模型（Insight/Trends/Funnels/Cohort/Survey/Flag/Replay）| Merism 没有这些概念 |
| ❌ ClickHouse / HogQL / Kafka | Postgres + pgvector + Redis 足够 |
| ❌ Plugin server | ADR 0001 —— 行为触发跑在 Celery beat |
| ❌ 多 research_goal flat list | platform spec Req 21.3/21.4，单字段为锚 |
| ❌ Temporal / LangGraph / Prefect | 单 LLM call 链 + Celery + event log 足够 |
| ❌ 自定义 LLM provider 接入（无 ADR） | DeepSeek + Qwen 全栈 |
| ❌ ClickHouse session replay | merism 不重放体验，只重放访谈转写 |

---

## 9. 开放问题

1. **AGENTS.md 规则 4 vs 实际 2-node** —— 需要决定：(a) 更新 AGENTS.md 与 platform spec Req 14.7 同步描述 2-node，或 (b) 把代码回退到单 call。当前选 (a)。
2. **Concept Testing 报告** —— `ConceptBlockViewSet.report` 已能返回 dimensions，但 Insights 页对 ConceptBlock 维度的可视化还没接通。
3. **Codebook 治理 UI** —— 后端完整，但 admin / 前端审批界面缺失（ROADMAP.md R16 后续项）。
4. **Email 渠道速率** —— 复用 IM 100 msg/h 限流，未来可能需要分渠道独立配额。
5. **`Study.research_objectives` vs `StudyGoal`** —— 一个是 JSON list（UI 编辑），另一个是结构化模型（覆盖度计算）。两者的同步策略尚未清晰：是单向导出还是双向绑定？
6. **i18n** —— `InterviewSession.locale` 字段已有，但 UI / prompt 还都是单语言。
7. **共享报告权限** —— `CustomReport.is_public + share_token` 已能公开，但没有限速 / 审计 / 撤销 UI。
8. **跨 study Knowledge Explore 页面** —— Repository scene 已有壳，但 ranking 仍是简单 RRF；按 goal similarity 重排尚未上线。

---

> 修订记录
>
> - **2026-05-20** 全面同步当前代码状态；新增 Concept Testing 2.0 / Codebook 治理 / Insights 三层 / Custom Reports / Link tracking / ServiceSettings / Cleaning pipeline / Invitation / Inbox / 2-node 主持人；移除 PostHog 引用；扩展 56 模型清单。
> - **2026-05-09** reset，取代 4 份旧规划文档。
