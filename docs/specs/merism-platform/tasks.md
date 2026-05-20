# Implementation Plan

> 说明：依赖关系见末尾的 Task Dependency Graph。任务号带 `_` 前缀的是子任务。
> 所有任务默认遵守 AGENTS.md 约束：`merism_` 前缀 db_table / `team_id` 隔离 / `~/lib/merism` primitives / Celery 里用 `merism.memai.capture.scoped_capture` / LLM 走 `merism.llm_gateway.client.get_client`。
> 每个任务完成后跑对应 pytest 入口（轻量 or ORM）+ ruff + pnpm typescript:check。

## Phase A：基础设施 + 数据模型

### A1. LLM / TTS / STT / Vision 客户端统一包装

- 在 `products/studies/backend/` 新增 `llm.py`, `tts.py`, `stt.py`, `vision.py`
- `llm.get_llm(model)` 返回 `merism.llm_gateway.client.get_client.OpenAI` 实例，`base_url=https://api.deepseek.com/v1`
- `tts.CosyVoiceClient.stream_tts(text_stream)` 返回 OGG/Opus 字节流
- `stt.ParaformerClient.stream_stt(audio_stream)` 返回 `STTEvent(partial|final, text, ts)`
- `vision.describe_frame(jpeg_bytes, context)` 返回 80–120 字描述
- `merism/settings/base.py` 的 MERISM annotated block 里加：`MERISM_DEEPSEEK_API_KEY`, `MERISM_QWEN_API_KEY`, `MERISM_QWEN_TTS_MODEL`, `MERISM_QWEN_STT_MODEL`, `MERISM_QWEN_VL_MODEL`, `MERISM_REPORT_SESSION_THRESHOLD`, `MERISM_SESSION_COST_ALERT_CENTS`, `MERISM_VIDEO_FRAME_INTERVAL_SEC`
- 轻量单测：mock httpx，断言 base_url / headers / 请求体
- _参考：Req 20, Req 23_

### A2. 数据模型扩展（单次 migration）

_A2.1 扩展已有模型_
- `Study` 增补/确认字段：`research_goal`, `research_background`, `hypothesis`, `success_metrics`, `status(枚举 6 态)`, `slug`, `owner`；确认 `db_table = "merism_study"` 和 `team_id`
- `InterviewGuide` 增加 `is_current: bool`，确认 sections JSON schema 文档
- `Participation` 增加 `is_preview: bool = False`
- `InterviewSession` 增加 `mode`, `vision_frames`, `cost_cents`；补齐 `audio_s3_key`, `video_s3_key`

_A2.2 新增模型_
- `Screener`（merism_screener）：`team`, `study (OneToOne 行为)`, `questions`, `pass_logic`
- `Stimulus`（merism_stimulus）：`team`, `study`, `kind`, `content`, `linked_question_ids`
- `StudyReport`（merism_study_report）：`team`, `study`, `content`, `charts`, `generated_at`, `generated_by`
- `CustomReportQuery`（merism_custom_report_query）：`team`, `study (null=True)`, `user`, `question`, `answer_markdown`, `chart_spec`, `citations`, `is_pinned`, `is_saved_insight`

_A2.3 索引_
- 按设计的索引清单加 `indexes` 到每个 Meta
- `Study.slug` unique，`Participation.slug` unique
- `CustomReportQuery (team_id, study_id, -created_at)` 和 `(team_id, user_id, -created_at)`

_A2.4 Migration_
- 调用 `/django-migrations` skill，生成单次 migration（只加列 + 建表，不做 data migration）
- Data migration 另起一个 migration：已有 Study row 若 `research_goal` 为空，从第一个 StudyGoal 取文本填入（保留 StudyGoal 表）
- ORM 测试：每张新表能 create + team 过滤生效
- _参考：Req 1, Req 3, Req 4, Req 6, Req 8, Req 12, Req 16, Req 17, Req 18, Req 21_

### A3. DRF serializer + team scoping 基座

- 每个新模型一个 serializer：`StudySerializer`, `InterviewGuideSerializer`, `ScreenerSerializer`, `StimulusSerializer`, `StudyReportSerializer`, `CustomReportQuerySerializer`
- 字段 `help_text` 填充（流入 OpenAPI → 前端类型）
- 统一用 `@extend_schema` 或 `@validated_request` 标注 viewset 方法
- 所有 viewset 通过 `self.context["get_team"]()` 获取 team；queryset 强制 `filter(team=...)`
- 调用 `/improving-drf-endpoints` skill 保证符合项目规范
- ORM 测试：跨 team 访问返回 404
- _参考：Req 22_

---

## Phase B：Study CRUD + Outline

### B1. Study viewset

- `POST /api/projects/:team_id/studies/`：只要 `research_goal` 非空即可创建；`status=draft`；生成 slug（32 字节 URL-safe）
- `GET /:id/`, `PATCH /:id/`
- `POST /:id/launch/` → `status=recruiting`（前置：`status in (ready, closed)` 才允许）
- `POST /:id/close/` → `status=closed`
- `POST /:id/preview_session/`：authed 端点，校验 team membership；创建 preview InterviewSession（或临时 Redis-only state），返回 `{session_id, ws_url}`；不创建正式 Participation，不 enqueue analysis；preview 不再走 `/i/:slug` 外部链接路径
- ORM 测试 + 参数化：各 status 转移合法性；preview_session 跨 team 返回 404；preview 结束后无 Participation / SessionInsight 落库
- _参考：Req 1, Req 8_

### B2. Guide 生成 + 保存

- 复用 `products/studies/backend/guide_generator.py`
- `POST /:id/generate_guide/`：基于 `research_goal` 调 LLM → 返回 sections JSON；写新 row `version=1, is_current=True`
- `GET /:id/guide/`：返回 `is_current=True`
- `POST /:id/guide/`：前端整体保存；新 row `version+=1`，旧版本 `is_current=False`（事务内）
- 轻量单测：sections JSON schema 校验（question 必须含 id/text/followup_depth/required/probe_directions/linked_stimulus_ids）
- _参考：Req 4_

### B3. Outline Review Service（对话式审查）

_B3.1 Service 实现_
- 新建 `products/studies/backend/outline_review.py`：`OutlineReviewService.review(study, chat_history, user_message) -> StreamingResponse`
- prompt 按设计文档 skeleton 构造（research_goal + current_guide + review_dimensions + rules + chat_history）
- 使用 OpenAI function calling tool `review_outline`
- 流式返回：先流 `reply_markdown` 文本，末尾追加 `proposed_changes` 和 `awaiting_user_decision`（SSE event 类型：`delta`, `tool_call`, `done`）

_B3.2 Endpoint_
- `POST /studies/:id/review_outline/`：SSE 返回
- `POST /studies/:id/apply_outline_changes/`：body `{proposed_changes: [...]}` → 在事务中 patch sections JSON → 写新版本
- `POST /studies/:id/finalize_outline/`：锁定 guide，`study.status → ready`

_B3.3 Apply 逻辑_
- `modify_question`：按 question_id 替换 text（或指定字段）
- `insert_question`：在 after_id 后插入
- `remove_question`：按 id 删除
- 参数化测试：三种 op 组合 + 边界（after_id 不存在、question_id 重复）
- snapshot 测试 prompt：对同一 guide，prompt 输出稳定
- mock LLM 响应测试 SSE 解析
- _参考：Req 5_

### B4. Screener / Stimulus viewsets

- `GET/PUT /studies/:id/screener/`：单 screener（如不存在则 PUT 创建）
- `POST /studies/:id/screener/generate/`：自然语言 → LLM → 结构化 questions + pass_logic 草稿
- `GET/POST /studies/:id/stimuli/` 列表/上传；上传走 `merism.services.storage`，key = `merism/stimuli/{study_id}/{filename}`
- `PATCH/DELETE /studies/:id/stimuli/:sid/`
- 大小/MIME 校验：图 10MB / 视频 100MB / PDF 20MB
- ORM 测试：`pass_logic` DSL 正确返回 pass/fail
- _参考：Req 3, Req 6_

---

## Phase C：受访者公开端点 + 访谈房间后端

### C1. 受访者公开 API（免登录）

- `GET /i/:slug/`：按 slug 查 Study，返回 consent 文本 + screener schema（不暴露 team_id / study_id / owner）
- `POST /i/:slug/screener/submit/`：对 screener 答案应用 `pass_logic`，返回 pass/fail；若 pass，创建 `Participation(status=started, source=public_link)`
- `POST /i/:slug/start/`：body `{mode}`；创建 InterviewSession，返回 session_id + WS URL。不接受 `is_preview` / `preview_token` 参数，preview 走独立的 authed 端点（见 B1）
- `POST /i/session/:id/upload/`：附件上传到 S3，返回 URL
- `POST /i/session/:id/complete/`：标记 session 完成，enqueue `analyze_session`（preview session 从独立端点进入，不走此路径）
- ORM 测试：公开端点不接受 preview 参数（传了也不生效）；preview 路径不污染 Participation 表
- _参考：Req 8, Req 9, Req 15, Req 22_

### C2. ConvState + Interview Moderator Service

_C2.1 ConvState_
- 新建 `products/studies/backend/interview_state.py`：`ConvState` dataclass（见设计文档）
- 持久化到 Redis，key = `merism:conv:{session_id}`，TTS 30 min
- 轻量单测：`remaining_followups()` / `advance_question()` / `record_followup()` 状态机

_C2.2 Moderator Service_
- 新建 `products/studies/backend/interview_moderator.py`：`ModeratorService.next_turn(state, user_utterance, attachment_ctx?)`
- prompt 按设计 skeleton（research_goal + current_question + stimulus_active + remaining_followups + vision_context）
- function schema `next_turn` 强制返回 `{spoken_text, next_action, next_question_id?}`
- 解析后做 guard：若 `remaining_followups == 0` 且 LLM 返回 `followup`，强制改为 `move_on`
- 流式 yield `spoken_text` token（给 TTS + caption）；末尾解析 tool call 更新 state
- 参数化测试：`followup_depth ∈ {0,1,2,3}` 下的预算耗尽行为
- snapshot 测试 prompt：不同 mode / stimulus 组合
- _参考：Req 14_

### C3. WebSocket endpoint

- 新建 `products/studies/backend/interview_ws.py`（Django Channels consumer 或 ASGI WebSocket）
- 消息协议按设计文档（client: audio_chunk / upload_attachment / end；server: stt_partial / stt_final / tts_chunk / caption / stimulus_change / session_end）
- 上行音频 → `stt.ParaformerClient.stream_stt` → 产出 partial/final → 回推 client
- Final transcript segment → 调 `ModeratorService.next_turn` → 边流式返回 `spoken_text`：一路进 `tts.CosyVoiceClient` 回推 tts_chunk，一路直接回推 caption
- `stimulus_change` 消息：当 `state.stimulus_active` 变化时推送
- 断线重连：WS 重新连接后从 Redis 恢复 ConvState + 已累积 transcript
- 集成测试（ORM + mock LLM/TTS/STT）：模拟一轮完整对话
- _参考：Req 11, Req 12, Req 14_

### C4. 视频模式抽帧

- `POST /i/session/:id/frame/`：前端每 `MERISM_VIDEO_FRAME_INTERVAL_SEC` 秒上传一张 JPEG
- 后端 `asyncio.create_task` 调 `vision.describe_frame`，写入 `InterviewSession.vision_frames` 并更新 Redis ConvState 的 `last_vl_description`
- 测试：只在 `mode=video` 时抽帧；audio 模式直接返回 204
- _参考：Req 12_

### C5. Session 结束 + 录制存储

- `complete` endpoint 里：flush transcript 到 Postgres、把 Redis ConvState 清掉、enqueue `analyze_session`（preview session 从独立端点来，跳过 enqueue）
- **仅 video 模式**：前端通过预签名 URL 分段上传 webm（音频内嵌视频轨）到 S3，key = `merism/sessions/{session_id}/video.webm`；complete 时记录 `video_s3_key`
- **audio 模式**：不上传任何录制文件；音频帧实时喂 STT 后即丢弃；`audio_s3_key` 保持空字符串，S3 上不产生任何该 session 的对象
- `reap_stale_sessions` Celery beat：每 5 分钟扫描 `started > 30 min` 无活动的 session，标为 `dropped`，enqueue analysis（若 transcript 长度 > 阈值）
- ORM 测试：audio 模式结束后 `audio_s3_key == ""` 且 S3 上无该 session 的任何对象；video 模式有 `video_s3_key` 非空
- _参考：Req 12, Req 14, Req 23_

---

## Phase D：Analysis / Custom Report / Knowledge

### D1. 个体分析 Celery task

- `analyze_session(session_id)` 在 `products/studies/backend/tasks.py`（或 analysis.py）
- 跳过 `participation.is_preview=True`
- 调 LLM（`deepseek-reasoner`）with function `emit_session_insight`
- 输出写 `SessionInsight`（update_or_create）
- 所有埋点用 `merism.memai.capture.scoped_capture`（`insight_generated` 事件带 team_id / study_id / session_id）
- Max retries 3，失败通知 study owner
- 参数化测试：transcript 长度 / mode / research_goal 类型变化下维度推导合理
- _参考：Req 16, Req 23, Req 27_

### D2. 群体报告 Celery task

- `generate_study_report(study_id)`：按设计的 6 步（收集 insights → 维度聚类 → 按 guide question 聚合 → 按维度聚合 → 挑 quote → 汇总 exec_summary）
- `POST /studies/:id/generate_report/` 触发 enqueue
- 自动触发：当 completed session 数 >= `MERISM_REPORT_SESSION_THRESHOLD` 时，自动 enqueue（首次）
- 写 `StudyReport.content`（含 exec_summary / quant_panel / qual_panel / insight_nuggets）+ `charts`
- 埋点 `study_report_generated`
- _参考：Req 17, Req 27_

### D3. Custom Report Service

_D3.1 Retriever_
- 新建 `products/studies/backend/custom_report.py`：`_retrieve(team_id, study_id, query)` 返回 transcript chunks + insights
- MVP：Postgres 全文搜索 + 维度过滤
- 留 hook 后续切 pgvector（对接 `s5-pgvector-embedding` spec）

_D3.2 Tool executor_
- `aggregate_tag(tag_name)` → 遍历 SessionInsight.tags 统计分布
- `filter_sessions(criteria)` → 应用 criteria 过滤 session_ids
- `cite_quote(session_id, ts_start, ts_end)` → 返回 transcript span + speaker

_D3.3 Service + endpoint_
- `CustomReportService.ask(...)` 按设计流程
- `POST /studies/:id/custom_reports/`：同步返回 answer + chart_spec + citations
- `GET /studies/:id/custom_reports/`：历史列表
- `PATCH /custom_reports/:id/`：`is_pinned` / `is_saved_insight` toggle
- 测试：mock LLM 返回 tool call，验证 tool executor 被调、结果注入
- _参考：Req 18_

### D4. Knowledge Explore（跨 study）

- `GET /knowledge/`：返回统计（team 下 study 数 / session 数）+ 最近 CustomReportQuery 列表 + 建议问题（静态 3 条）
- `POST /knowledge/ask/`：调 `CustomReportService.ask(study_id=None, team_id, user, question)`
- Citation 带 `study_name`
- 特性门控 `MERISM_KNOWLEDGE_EXPLORE`
- ORM 测试：跨 study 检索按 team 隔离
- _参考：Req 19_

### D5. 成本记账 + 告警

- 每次 LLM/TTS/STT/Vision 调用返回后，把估算成本累加到 `InterviewSession.cost_cents`（简单按 token × rate 或 duration × rate）
- Celery beat `check_session_cost_alerts`：扫描 `cost_cents > MERISM_SESSION_COST_ALERT_CENTS` 的 session，写一条 InboxItem.kind=cost_alert 给 owner
- 复用 `/sending-notifications` skill 集成通知
- _参考：Req 23_

---

## Phase E：招募 + CowAgent

### E1. Recruit endpoints

- `GET /studies/:id/recruit/link/`：仅 `status >= ready` 返回公开链接
- `POST /studies/:id/recruit/broadcast/`：body `{channel_id, message_template, recipients}` → 调用已有 `products/studies/backend/recruitment/` adapter
- `GET /studies/:id/recruit/deliveries/`：投递状态列表（复用 `cowagent-im-recruitment` spec 的 Delivery_Record）
- _参考：Req 7_

---

## Phase F：前端 Create + Study Scene + Outline

### F1. Create Study Modal

- `products/studies/frontend/create/CreateStudyModal.tsx` + `createStudyLogic.ts`（kea）
- 单输入框 `Textarea`（from `~/lib/merism`），占位符示例
- 可折叠 disclosure：假设 / 成功指标 / 研究背景
- 调用生成的 API 类型（`hogli build:openapi` 后）
- Tailwind 布局，不写内联 style
- Jest 测试：输入空态禁用按钮 / 成功跳转
- _参考：Req 1, Req 24_

### F2. Study Scene + Tabs 路由

- `products/studies/frontend/study/StudyScene.tsx`：顶部面包屑 + 8 tabs
- kea router 对接 URL `?tab=brief` 默认
- 权限：owner/admin 才显示 Settings 的危险操作
- 空 tab 组件占位
- _参考：Req 2_

### F3. Brief / Screener / Stimuli tabs

- `brief/`：展示 research_goal + background + hypothesis + dashboard（完成数 / 完成率）
- `screener/`：问题编辑器（复用 merism primitives 的 Input/Select），自然语言转结构化按钮
- `stimuli/`：列表 + 上传；每张卡片显示关联 questions
- 使用生成的 API 类型
- Jest 测试：上传 → 列表刷新
- _参考：Req 3, Req 6_

### F4. Outline Editor

_F4.1 主编辑器_
- `outline/OutlineEditor.tsx`：section 折叠 + 拖拽；question 卡片拖拽
- `QuestionCard.tsx`：text 行内编辑 / followup_depth 滑块 (0–3) / required 开关 / stimulus 下拉 / probe_directions chips
- kea logic 管理 sections 状态，保存时 POST `/guide/`

_F4.2 AI 审查抽屉_
- `OutlineReviewDrawer.tsx`：右侧抽屉，`outlineReviewLogic.ts`
- 连接 SSE `/review_outline/`，增量渲染 `reply_markdown`；解析 `proposed_changes` 显示"接受 / 全部接受 / 应用"按钮
- Apply → POST `/apply_outline_changes/` → 刷新 guide
- Jest 测试：mock SSE，断言按钮渲染 + 应用后刷新
- _参考：Req 4, Req 5_

---

## Phase G：受访者前端（Consent → 准备 → 房间）

### G1. Consent + Screener + 准备页

- `interview/consent/ConsentPage.tsx` → `ScreenerPage.tsx` → `PrepPage.tsx`
- URL：`/i/:slug`、`/i/:slug/screener`、`/i/:slug/prep`
- PrepPage 根据 Study 允许的 mode 显示单选或双选；提供麦克风测试（WebAudio API + 画波形）+ 视频预览（getUserMedia）
- 不调用 authed API，使用公开端点
- Jest 测试：consent 未勾选禁用继续 / screener 不通过 → 感谢页
- _参考：Req 9, Req 10_

### G2. Interview Room 布局

- `interview/InterviewRoom.tsx`：`h-screen bg-gray-100` + 顶部白色导航 + 左 2/3 / 右 1/3
- `InterviewLeftPane.tsx`：AI INTERVIEWER tag + 问题文本 + BeginResponse 按钮 + PreviewFrame
- `InterviewRightPane.tsx`：实时字幕流 + 附件上传 + 消息流 + 文字降级输入
- `PreviewFrame` 组件：mode=audio 显示占位 + 波形 / mode=video 显示摄像头 / stimulus_active 时覆盖 stimulus
- 全部 primitives from `~/lib/merism`
- _参考：Req 11, Req 13, Req 24_

### G3. Interview Logic（kea）+ WS

- `interviewLogic.ts`：打开 WS、处理 `stt_partial` / `stt_final` / `tts_chunk`（MediaSource 播放） / `caption` / `stimulus_change`
- 视频模式：每 10 秒 canvas drawImage → toBlob(jpeg) → POST `/frame/`
- 文字降级输入：通过 HTTP 提交 → 后端伪造 STT final 事件
- 自测模式：由 Study 详情页按钮（见 F5）启动，logic 接收 `isPreview: true` 初始参数；右下角渲染橙色"自测模式"角标 + "退出自测"按钮（点击返回 Study 详情页）；preview 走 authed WS URL，不走 `/i/:slug`；preview 结束不展示受访者感谢页，直接回 Study 详情
- Jest 测试：mock WS 事件序列 → 断言 state 变更；isPreview=true 时角标可见、退出按钮跳转
- _参考：Req 8, Req 12, Req 13, Req 14, Req 15_

### F5. Study 详情页 "Test your interview" 按钮

- 在 Outline tab 和 Recruit tab 顶部添加 "Test your interview" 按钮（`~/lib/merism/primitives` Button），仅 `study.status >= ready` 时可见
- 点击 → POST `/api/projects/:team_id/studies/:id/preview_session/` → 拿到 `session_id` + `ws_url`
- 路由到内部 preview 视图（复用 `InterviewRoom` 组件，跳过 consent / screener / prep，直接进房间），`isPreview=true` 传入 `interviewLogic`
- 权限：仅 team 成员可见按钮；非成员即便拿到 URL 也 404
- Jest 测试：`status < ready` 时按钮不渲染；点击后路由跳转到 preview 房间
- _参考：Req 8_

---

## Phase H：Analysis + Knowledge 前端

### H1. Analysis 页主区

- `analysis/AnalysisPage.tsx`：`flex`，主区 + 右侧 400px sidebar
- `MainReport.tsx`：拉 `GET /report/`；按 Guide Question 渲染 `grid-cols-12`（左 5 定量 + 右 7 定性）
- 图表组件 `MerismBarChart`（ECharts 封装）：最高柱蓝色，其余灰
- Insight nuggets 卡片行
- 空态（session 数 < 阈值）显示"等待访谈数据"
- _参考：Req 17, Req 2_

### H2. Custom Report Sidebar

- `CustomReportSidebar.tsx`：`flex flex-col h-screen` 固定右侧；顶部 header、中间消息流（`overflow-y-auto`）、底部输入框
- 提交 → POST `/custom_reports/` → 渲染 `answer_markdown` + 图表 + citations
- Citation 点击：触发 `openTranscriptAt(session_id, ts)` 事件（后续对接 transcript viewer）
- 钉 / 保存按钮调 `PATCH /custom_reports/:id/`
- Jest 测试：提问 → 答案渲染 / 图表渲染 / citation 链接
- _参考：Req 18_

### H3. Knowledge Explore 页

- `knowledge/KnowledgeExplorePage.tsx`：大输入框 + 建议问题 + 过滤器 + 最近问答
- 提交跳转到复用 `CustomReportSidebar` 风格的答案视图（study_id 为空）
- Citation 多一个 `study_name` 前缀
- _参考：Req 19_

---

## Phase I：横切关注点

### I1. 埋点

- 所有关键事件通过 `structlog` + Langfuse（web 路径）或 `merism.memai.capture.scoped_capture`（Celery 路径）
- 事件列表：`study_created`, `outline_finalized`, `recruit_link_generated`, `participation_started`, `session_completed`, `insight_generated`, `study_report_generated`, `custom_report_query_submitted`
- 每个事件必带 `team_id`；涉及 study 的带 `study_id`；涉及用户的带 `user_id`
- _参考：Req 27_

### I2. OpenAPI + 前端类型生成

- 每个 viewset/serializer 写完后：`hogli build:openapi`
- 前端改用生成的类型（不写手工 API 类型）
- 调用 `/adopting-generated-api-types` skill 迁移
- _参考：Req 22 (隐含的 API schema)_

### I3. E2E Playwright 测试

- `products/studies/frontend/e2e/`（或根据项目 e2e 目录）
- 场景 1：研究者创建 study → 生成提纲 → 自测访谈（LLM mocked）→ 看 insight → 提 custom report
- 场景 2：受访者 consent → screener → 准备页 → 房间完成一轮 → 完成页
- 跑 `hogli test`（自动检测）
- _参考：Req 1–19_

### I4. 非目标验证（反向测试）

- 单测：不存在 `StudyGoal` 写入路径（grep 确认）
- 单测：不存在独立 policies 表的新写入
- 代码审查清单：不引入 plugin-server / DashScope 特定 endpoint / LemonUI 在新 Merism surface
- _参考：Req 26, Req 21_

---

## Task Dependency Graph

```
A1 (LLM/TTS/STT/Vision clients)
 └─▶ B2, B3, C2, D1, D2, D3
A2 (models + migration) ─▶ A3 (serializer base)
A3 ─▶ B1, B4, D1, D2, D3, D4, E1
B1 ─▶ B2 ─▶ B3 ─▶ B4 (同 Study tab)
B1 ─▶ C1 (公开端点依赖 Study)
C1 ─▶ C2 ─▶ C3 ─▶ C4 ─▶ C5
C5 ─▶ D1 ─▶ D2
A3 + A1 ─▶ D3 ─▶ D4
C5 ─▶ D5
B4, E1 可并行于 B3 之后

前端：
I2 (OpenAPI) 依赖 B1, B2, B3, B4, C1, D1, D2, D3, D4, E1 的 API 完成
F1 ─▶ F2 ─▶ F3, F4
F2 ─▶ F5（F5 依赖 B1 的 preview_session endpoint）
F4 可并行 G1
G1 ─▶ G2 ─▶ G3（G3 依赖后端 C3 WS；F5 启动 preview 时复用 G3）
H1 依赖 D2 完成；H2 依赖 D3；H3 依赖 D4
I1 贯穿所有；I3 在 H2/H3 之后；I4 在 A2 完成后即可开始
```

关键路径：`A1 → A2 → A3 → B1 → B2 → B3 → C1 → C2 → C3 → C5 → D1 → D2 → H1`

---

## 建议的 Sprint 切分

- **S1**：A1 + A2 + A3（基础设施）
- **S2**：B1 + B2 + B3 + F1 + F2 + F4 + F5（Study + Outline 闭环，含自测按钮）
- **S3**：B4 + C1 + G1 + F3（Screener / Stimuli / 受访者 consent 链路）
- **S4**：C2 + C3 + C4 + C5 + G2 + G3（受访者访谈房间 端到端）
- **S5**：D1 + D2 + H1（个体 + 群体分析）
- **S6**：D3 + D4 + D5 + H2 + H3（Custom Report + Knowledge + 成本告警）
- **S7**：E1 + I1 + I2 + I3 + I4（招募 + 横切）

每个 Sprint PR 用 `feat(studies/Sx.y): ...` 格式，包含 `Refs: / Flag: / Rollback: / Verification:` headers（见 SPRINT_RUNBOOK.md）。