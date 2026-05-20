# Requirements Document

## Introduction

Merism 是一个 AI 驱动的用户研究平台。研究者写一个研究目标，AI 帮他拟访谈提纲并审查修改，通过 CowAgent 群发或公开链接招募受访者；受访者进入房间与 AI 主持人进行音频/视频访谈；AI 自动做个体分析与群体综合，生成带引用、带可视化的结构化报告；多个研究沉淀成跨库问答知识库。

本文档是 `standalone/PRODUCT.md` 的需求正式化。所有设计决策以 PRODUCT.md 为源真，本文档用 EARS 格式给出可验证的验收标准。

核心原则:
- **Research Goal 是唯一的北极星**: 创建 study 的第一步就是输入研究目标,此后每个 AI 环节(提纲生成/审查/访谈主持/个体分析/群体综合/Custom Report/知识库)都以它为锚点
- **分析维度不做独立 UI**: tag / dimension schema 由 AI 从 `research_goal + outline_questions` 自动推导
- **多 goal 文本字段**: 使用 `Study.research_goal: TextField`,不使用 Phase 0 遗留的 `StudyGoal` 多 goal flat list
- **Team 隔离**: 所有租户数据模型必须带 `team_id`; 所有 Merism 表使用 `merism_` db_table 前缀

## Glossary

- **Study**: 一次研究,绑定一个 `research_goal` 文本字段,是所有数据的顶层聚合根
- **Research_Goal**: study 唯一必填的研究目标(一句话自然语言),贯穿 AI 的每个环节
- **Interview_Guide**: 访谈提纲,包含多个 sections,每个 section 包含多个 questions
- **Question**: 提纲中的单个问题,含 text / followup_depth(0-3) / required / probe_directions / linked_stimulus_ids
- **Screener**: 受访者筛选问卷,决定受访者是否符合研究条件
- **Stimulus**: 刺激物(图片/视频/PDF/文字块/外链),可关联到某个或某些 question
- **Participation**: 受访者的参与记录,对应唯一邀请链接 slug
- **Interview_Session**: 一次访谈会话(音频或视频模式),含 transcript / video_s3_key(仅视频模式) / vision_frames(仅视频模式)。音频模式只保留 transcript, 不存音频文件
- **Session_Insight**: 单场访谈的个体分析结果(summary / highlights / tags / extracted_tasks)
- **Study_Report**: 一个 study 的结构化群体报告(exec_summary / quant_panel / qual_panel / insight_nuggets)
- **Custom_Report_Query**: 用户在分析页 sidebar 提的一次问答,含 answer_markdown / chart_spec / citations
- **Outline_Review_Agent**: 对话式审查提纲的 AI(返回 proposed_changes 列表)
- **Interview_Moderator_Agent**: 主持访谈的流式 AI(每个 user turn 在同一个 `stream_turn` 协程内顺序两次 LLM call: 非流式 `coverage_steer` 决策 → 流式 `generate` 生成,详见 Req 14)
- **Analysis_Agent**: 个体 + 群体分析 + Custom Report 的 AI
- **Preview_Mode**: 研究者在 Study 详情页点击 "Test your interview" 按钮进入的自测模式, 走 authed 路径, 不写真实 Participation / Session, 不扣配额, 不生成外部链接
- **Knowledge_Explore**: 跨 study 的问答知识库页,检索所有 study 的 session 内容

## Requirements

### Requirement 1: 创建 Study(唯一必填 research_goal)

**User Story:** As a 研究者, I want 通过最简输入框创建一个新研究,只必填 research_goal, so that 我不被多余字段干扰,快速进入核心工作流。

#### Acceptance Criteria

1. WHEN 研究者打开 Create Study Modal, THE System SHALL 只显示一个主输入框"你这次要研究什么?"并提供占位符示例(如"调研 18-25 岁用户对 XX 零食的口味满意度")。
2. THE Create Study Modal SHALL 把"添加假设 / 成功指标 / 研究背景"作为可折叠的可选区域,默认折叠。
3. WHEN 研究者点击"下一步"且 `research_goal` 非空, THE System SHALL 创建 `Study(research_goal=...)` 并跳转到 Study 详情页 Brief tab。
4. IF `research_goal` 为空或仅含空白字符, THEN THE System SHALL 禁用"下一步"按钮并在字段下方提示"请填写研究目标"。
5. THE Study 模型 SHALL 使用 `merism_study` 作为 `db_table`, 且必须包含 `team_id` 作为租户隔离字段。
6. THE Study.status SHALL 为枚举 `[draft, ready, recruiting, active, closed, archived]`, 初始值为 `draft`。

### Requirement 2: Study 详情 Tab 导航

**User Story:** As a 研究者, I want 在 Study 详情页通过 tab 在不同工作区间切换, so that 我能按照研究者流程顺畅推进每一步。

#### Acceptance Criteria

1. THE Study 详情页 SHALL 包含 8 个 tabs, 固定顺序: Brief / Outline / Screener / Stimuli / Recruit / Analysis / Knowledge / Settings。
2. WHILE `Study.status == draft` 且提纲未 finalize, THE Recruit tab SHALL 禁止生成公开链接并显示提示"请先完成提纲"。
3. WHILE `Study.status IN (draft, ready)` 且尚无任何已完成的 session, THE Analysis tab SHALL 显示空态引导"等待访谈数据"。
4. WHERE 当前用户不是 study owner 或 team admin, THE Settings tab SHALL 隐藏"删除 / 归档"危险操作。
5. THE Brief tab SHALL 展示 research_goal、background、hypothesis 以及 dashboard(进度、完成数、完成率)。

### Requirement 3: Screener 配置

**User Story:** As a 研究者, I want 用自然语言描述筛选条件,系统转为结构化的 screener 问题, so that 受访者进入访谈前能被有效过滤。

#### Acceptance Criteria

1. THE Screener 模型 SHALL 使用 `merism_screener` 作为 `db_table`, 含 FK 到 Study 和 `team_id`。
2. THE Screener.questions SHALL 为 JSONField, 每个 question 含 `text`, `type ∈ {single, multi, range}`, `options`。
3. WHEN 研究者输入自然语言描述(例:"过去 30 天买过零食的 18-25 岁在校生"), THE System SHALL 调用 LLM 生成结构化 screener 草稿, 研究者可在编辑器中修改。
4. THE Screener.pass_logic SHALL 为 JSONField, 描述哪些答案组合视为通过。
5. WHEN 受访者提交 screener 答案且不满足 `pass_logic`, THE System SHALL 显示感谢页并不创建 Interview_Session。

### Requirement 4: 提纲编辑器

**User Story:** As a 研究者, I want 编辑提纲的 section 和 question, 配置每题的追问深度/必答/关联刺激物, so that 访谈流程按我预期进行。

#### Acceptance Criteria

1. THE Interview_Guide 模型 SHALL 使用 `merism_interview_guide` 作为 `db_table`, 含 FK 到 Study、`team_id`、`version: Int`。
2. THE Interview_Guide.sections SHALL 为 JSONField, 结构为 `[{id, title, questions: [...]}]`。
3. THE 每个 Question SHALL 含 `id`, `text`, `followup_depth ∈ [0, 3]`, `required: bool`, `probe_directions: string[]`, `linked_stimulus_ids: string[]`。
4. WHEN 创建新 Study 后首次进入 Outline tab, THE System SHALL 调用 Guide Generator 基于 `research_goal` 生成提纲初稿。
5. THE 提纲编辑器 SHALL 支持拖拽重新排序 section 与 question, 折叠/展开 section, 增删 question。
6. WHEN 研究者修改提纲并保存, THE System SHALL 创建新的 `InterviewGuide.version`, 保留历史版本。
7. THE 每个 Question 卡片 SHALL 在 UI 上展示: 问题文本 / 追问深度选择器 / 必答开关 / 刺激物关联下拉 / 探针方向列表。

### Requirement 5: Outline Review Agent(对话式审查)

**User Story:** As a 研究者, I want 点击"让 AI 审查"后与 AI 来回对话修改提纲, so that 我能在正式招募前消除 privacy / ordering / bias 等问题。

#### Acceptance Criteria

1. WHEN 研究者点击"✨ 让 AI 审查"按钮, THE System SHALL 在右侧打开 chat 抽屉并把当前提纲 JSON 发给 Outline_Review_Agent。
2. THE Outline_Review_Agent SHALL 通过 function calling 返回结构化输出 `{reply_markdown, proposed_changes: [{op, ...}], awaiting_user_decision}`。
3. THE proposed_changes.op SHALL 支持至少三种操作: `modify_question` / `insert_question` / `remove_question`。
4. THE Outline_Review_Agent SHALL 在至少六个维度审查: privacy(PII 问题) / ordering(冷热度) / structure(warmup→core→closing) / bias(引导性、双重否定) / 与 research_goal 对齐 / followup_depth 是否合理。
5. THE Outline_Review_Agent SHALL NOT 代替用户决定,回复必须以"你希望……?"的形式结尾,不主动修改。
6. WHEN 研究者在 chat 中点击"接受"或"全部接受", THE System SHALL 按 proposed_changes 逐条 apply 到当前提纲并创建新版本。
7. WHEN 研究者在 chat 中继续对话(如辩护某条建议), THE Outline_Review_Agent SHALL 在下一轮响应中理解上下文并可能修改或撤回之前的 proposed_changes。
8. THE Outline_Review_Agent 的 LLM 调用 SHALL 通过 `merism.llm_gateway.client.get_client` 包装器进行,以记录 trace 和成本。

### Requirement 6: Stimuli 管理

**User Story:** As a 研究者, I want 上传并管理全 study 级的刺激物(图片/视频/PDF/文字/外链), 关联到具体问题, so that 访谈时 AI 能在该题展示对应素材。

#### Acceptance Criteria

1. THE Stimulus 模型 SHALL 使用 `merism_stimulus` 作为 `db_table`, 含 FK 到 Study、`team_id`。
2. THE Stimulus.kind SHALL 为枚举 `[image, video, text, pdf, link]`。
3. THE Stimulus.content SHALL 为 JSONField `{url, text, title, description}`。
4. THE System SHALL 支持上传 jpg/png/gif(图片)、mp4/webm(视频)、pdf、纯文字块、外链。
5. THE 上传文件 SHALL 通过 `merism.services.storage`(S3/MinIO via boto3)写入 S3。
6. THE Stimulus.linked_question_ids SHALL 为 JSONField, 记录该刺激物关联的 question id 列表。
7. THE 提纲编辑器的每个 Question SHALL 允许关联 1 个或多个 `stimulus_id`。
8. WHERE 某题被标记为 active 且关联了 stimulus, THE 受访者房间的左 2/3 预览框 SHALL 覆盖展示对应 stimulus。

### Requirement 7: 招募链接与 CowAgent 集成

**User Story:** As a 研究者, I want 提纲 finalize 后自动生成公开访谈链接并可通过 CowAgent 群发到飞书/企微/QQ, so that 我能快速触达目标受访者。

#### Acceptance Criteria

1. WHEN 研究者在 Outline tab 点击"finalize"且提纲有效, THE System SHALL 生成唯一的公开访谈链接 `/i/:slug` 并将 `Study.status` 更新为 `ready`。
2. THE Recruit tab SHALL 同时提供两条路径: 复制公开链接 和 通过 CowAgent 群发配置。
3. THE CowAgent 群发 SHALL 复用 `products/studies/backend/recruitment/` 下已有的 adapter(飞书 / 企微 / QQ)。
4. WHEN 通过 CowAgent 群发失败(如凭证失效), THE System SHALL 在 Recruit tab 显示错误原因并保留已成功投递的记录。
5. WHILE `Study.status == draft`, THE Recruit tab 的"生成公开链接"按钮 SHALL 保持禁用。

### Requirement 8: 自测模式(Preview)

**User Story:** As a 研究者, I want 在 Study 详情页直接点一个 "Test your interview" 按钮进入自测, so that 我能验证提纲、刺激物、AI 主持效果都正常,不用复制带 token 的链接。

#### Acceptance Criteria

1. WHERE `Study.status >= ready`(提纲已 finalize), THE Study 详情页的 Outline tab 与 Recruit tab 顶部 SHALL 显示 "Test your interview" 按钮。
2. WHEN 研究者点击 "Test your interview" 按钮, THE System SHALL 在当前已登录会话中启动一个 preview session 并路由到内部 preview 访谈房间视图(无需 /i/:slug / 无需 token / 无需 consent / 无需 screener)。
3. WHILE 处于 Preview_Mode, THE System SHALL NOT 创建正式 Participation 记录(preview 用内存/Redis-only state 或 `is_preview=True` 的隔离记录,不计入招募完成数)。
4. WHILE 处于 Preview_Mode, THE System SHALL NOT enqueue `analyze_session`。
5. WHILE 处于 Preview_Mode, THE System SHALL NOT 扣减 study 配额。
6. WHILE 处于 Preview_Mode, THE 访谈房间 SHALL 在右下角显示橙色"自测模式"角标, 并提供"退出自测"按钮随时返回 Study 详情页。
7. THE Preview endpoint SHALL 鉴权: 仅 `study.team` 的成员可访问, 不要求是 study owner(团队内谁都可自测)。
8. THE System SHALL NOT 生成或暴露任何带 preview token 的外部 URL; preview 只在已登录 session 中通过 authed API 启动。

### Requirement 9: 受访者 Consent 与 Screener

**User Story:** As a 受访者, I want 进入邀请链接后先看到 consent 和 screener, so that 我清楚知道会被 AI 主持、会被录音/录像,且确认我是合适的受访者。

#### Acceptance Criteria

1. WHEN 受访者打开 `/i/:slug`, THE System SHALL 先展示 Consent 页(含: 将被 AI 主持、录音/录像同意、隐私条款)。
2. IF 受访者未勾选同意, THEN THE System SHALL 禁用"继续"按钮。
3. WHEN 受访者通过 consent 后, THE System SHALL 展示 Screener(1-3 道)。
4. IF 受访者的 screener 答案不满足 `Screener.pass_logic`, THEN THE System SHALL 显示感谢退出页并记录 `Participation.status = dropped`。
5. WHEN 受访者通过 screener, THE System SHALL 创建 `Participation(status=started, source=public_link 或 cowagent)` 并进入准备页。

### Requirement 10: 准备页(选择音频/视频、测设备)

**User Story:** As a 受访者, I want 进入访谈房间前选择音频或视频模式并测试麦克风/摄像头, so that 正式访谈时设备不掉链子。

#### Acceptance Criteria

1. WHERE Study 允许音频和视频两种模式, THE 准备页 SHALL 展示两个选项让受访者选择。
2. WHERE Study 只允许一种模式, THE 准备页 SHALL 跳过选择,直接进入对应测试。
3. WHEN 受访者选择音频模式, THE 准备页 SHALL 提供麦克风测试(显示波形)。
4. WHEN 受访者选择视频模式, THE 准备页 SHALL 提供麦克风和摄像头测试(显示实时预览)。
5. WHEN 设备测试通过且受访者点击"开始", THE System SHALL 创建 `Interview_Session(mode=audio|video)` 并跳转到访谈房间。

### Requirement 11: 受访者房间布局(左 2/3 / 右 1/3)

**User Story:** As a 受访者, I want 清晰的房间布局 ——左边是 AI 和我的摄像头/刺激物,右边是实时字幕和对话框, so that 我能专注回答问题同时看到对话内容。

#### Acceptance Criteria

1. THE 访谈房间 SHALL 采用 `h-screen` 全屏布局,背景 `bg-gray-100`,顶部固定白色导航中央展示 Logo。
2. THE 主体区域 SHALL 分为左 2/3 和右 1/3 两列。
3. THE 左 2/3 区域 SHALL 包含: "AI INTERVIEWER" 小灰标签、AI 当前问题文本(高行高)、"Begin response" 紫色大按钮(含摄像头图标)、摄像头预览/刺激物展示区。
4. THE 右 1/3 区域 SHALL 包含: 实时语音转写字幕、AI 字幕(跟 TTS 音频同步)、附件上传按钮(图片/视频/PDF)、消息流、文字输入框(退化选项)。
5. THE 访谈房间所有 UI primitives SHALL 从 `~/lib/merism` 导入(不得使用 LemonUI 组件)。

### Requirement 12: 音频模式 vs 视频模式差异

**User Story:** As a 受访者, I want 根据我选择的模式得到对应的体验, so that 我的隐私偏好被尊重,成本也随模式差异化。

#### Acceptance Criteria

1. WHILE 模式为 audio, THE 预览框 SHALL 显示占位图 + 波形, 摄像头不开启。
2. WHILE 模式为 video, THE 预览框 SHALL 显示用户摄像头实时画面。
3. WHILE 模式为 video, THE System SHALL 每 10 秒从视频流抽取一帧喂给 Qwen-VL-Max 生成 VL 描述。
4. WHILE 模式为 audio, THE System SHALL 仅保留 transcript 到 `InterviewSession.transcript`, 不存储任何音频文件 (`audio_s3_key` 恒为空字符串)。
5. WHILE 模式为 audio, THE 音频帧 SHALL 仅用于实时 STT, STT 产出 final transcript 后原始音频帧 SHALL 被直接丢弃, 不落盘不上传 S3。
6. WHILE 模式为 video, THE System SHALL 录制视频(音频内嵌视频轨)到 S3 并写入 `video_s3_key`; 音频不单独存储, `audio_s3_key` 保持空字符串。
7. WHILE 模式为 video, THE System SHALL 把 VL 描述追加到 `InterviewSession.vision_frames: [{ts, vl_description}]`。

### Requirement 13: 刺激物交互

**User Story:** As a 受访者, I want 某题展示刺激物时预览框覆盖显示,可手动关闭切回摄像头/波形, so that 我既能看到素材也不失去对自己画面的掌控。

#### Acceptance Criteria

1. WHEN 当前 active question 关联了 stimulus, THE 预览框 SHALL 覆盖展示该 stimulus。
2. WHEN 受访者点击预览框上的 "✕ 关闭", THE System SHALL 切回摄像头预览(视频模式)或波形(音频模式)。
3. WHEN stimulus 被展示时, THE Interview_Moderator_Agent 的 system prompt SHALL 注入 `<current_stimulus>` 标签含 stimulus 描述。

### Requirement 14: Interview Moderator Agent(流式主持)

**User Story:** As a 受访者, I want AI 主持人按提纲提问、基于我的回答追问、适时移到下一题, so that 访谈自然流畅且不跑题。

#### Acceptance Criteria

1. WHEN 一次 user turn 的 STT 产出 final transcript segment, THE Interview_Moderator_Agent SHALL 在同一个 `stream_turn` 协程内顺序执行两次 LLM 调用：(a) 非流式 `coverage_steer` 返回结构化 `ModeratorDecision` 含 `next_action ∈ [followup, move_on, clarify, close]` 与可选 `next_question_id` / `target_goal_id`；(b) 流式 `generate` 输出"下一句话"逐 token 推给 TTS。
2. THE Interview_Moderator_Agent SHALL 跟踪 conversation state: 当前题号 / 该题已追问次数 / 剩余追问预算 = `followup_depth - 已追问`。
3. IF 剩余追问预算 == 0 OR `probe_policy=none` 拒绝 followup, THEN THE `decision_validator` SHALL 在服务端覆写 LLM 决策为 `next_action = move_on`，**不**触发额外 LLM 调用。
4. THE coverage_steer prompt SHALL 包含: `<research_goal>`, `<current_question>`, `<current_stimulus>`(如有), `<remaining_followups>`, `<vision_context>`(视频模式,最近一帧 VL 描述), `<coverage_context>`(P0/P1/P2 goal 当前覆盖度), `<concept_context>`(若该题在 ConceptBlock 内)。
5. WHEN generate 节点产出文本时, THE System SHALL 并行两路: 文本喂给 Qwen CosyVoice 流式 TTS 推音频给浏览器 + 文本推字幕到右侧对话框。
6. WHEN closure 检查任一信号命中(close_decision / all_p0_answered / leaving_intent / idle_timeout / ws_disconnect / max_duration), THE System SHALL 结束 session 并跳转到受访者感谢页。
7. THE Interview_Moderator_Agent SHALL NOT 引入第三次 LLM 调用、macro/meso/micro 三层决策、或独立 policy 持久化模块(coverage_steer / engagement / off_topic 仅作为 prompt context, 不作为模块)。LangGraph / Prefect / 任意 agent framework 同样禁止。
8. THE Interview_Moderator_Agent 的 LLM 调用 SHALL 通过 `merism.llm_gateway.client.get_client(logical_name, *, team, trace_id)` 路由：优先读 team 的 ServiceSettings(每队 base_url + model + 加密 api_key),回退环境变量 `MERISM_LLM_*`。

### Requirement 15: 受访者附件上传

**User Story:** As a 受访者, I want 在访谈过程中上传图片/视频/PDF 给 AI, so that AI 能基于我的实物或文档做更具体的追问。

#### Acceptance Criteria

1. THE 右侧对话框 SHALL 提供附件上传按钮,支持 图片 / 视频 / PDF。
2. WHEN 受访者上传附件, THE System SHALL 把文件存到 S3 并把 URL + 描述喂给 Qwen-VL-Max 生成理解结果。
3. WHEN Qwen-VL 返回对附件的理解, THE Interview_Moderator_Agent SHALL 在下一轮的 system prompt 中注入附件理解作为 context,并基于附件内容追问。

### Requirement 16: 个体分析(Session Insight)

**User Story:** As a 研究者, I want 每场访谈结束后自动生成结构化的个体分析, so that 我不需要手动听录音也能快速了解每个受访者说了什么。

#### Acceptance Criteria

1. WHEN `InterviewSession` 结束(`next_action = close` 或受访者主动退出), THE System SHALL enqueue 一个 Celery task `analyze_session(session_id)`。
2. THE analyze_session task SHALL 调用 Analysis_Agent 一次 LLM(可用 DeepSeek Reasoner)生成 SessionInsight。
3. THE SessionInsight 模型 SHALL 使用 `merism_session_insight` 作为 `db_table`, 含 FK 到 Session、`team_id`。
4. THE SessionInsight SHALL 包含: `summary`(3-5 句) / `highlights: [{text, ts_start, ts_end, importance}]`(3-8 条) / `tags: {dimension_name: value}` / `extracted_tasks: [{title, category, priority, evidence_quote_id}]`。
5. THE tags 的维度 SHALL 由 Analysis_Agent 基于 `research_goal + outline_questions` 自动推导,不由用户配置。
6. WHEN Celery task 中需要埋点, THE System SHALL 使用 `merism.memai.capture.scoped_capture`(不使用 `structlog`/Langfuse 直接埋点, 后者在 Celery 中会静默丢事件)。

### Requirement 17: 群体分析(Study Report)

**User Story:** As a 研究者, I want 收集到足够 session 后生成结构化的群体报告, so that 我能一页内把握全局结论并向利益相关方汇报。

#### Acceptance Criteria

1. WHEN `Study` 已完成 session 数达到阈值 N(默认 10), OR 研究者手动触发, THE System SHALL 调用 Analysis_Agent 生成 `StudyReport`。
2. THE StudyReport 模型 SHALL 使用 `merism_study_report` 作为 `db_table`, 含 FK 到 Study、`team_id`、`generated_at`。
3. THE StudyReport.content SHALL 为 JSONField, 含四个 section: `exec_summary`(无边框灰底,结论先行) / `quant_panel`(定量,5/12 宽) / `qual_panel`(定性,7/12 宽) / `insight_nuggets`(卡片式)。
4. THE quant_panel SHALL 为每个 Guide Question 生成柱状图,最高柱蓝色高亮,其余灰色。
5. THE qual_panel SHALL 展示富文本 + quote 卡片(含 `[▶]` 播放按钮 / 受访者名 / 时间戳)。
6. THE insight_nuggets SHALL 为 3-6 张卡片,每张含 icon / 标题 / 数据(如"73% 受访者提到…")。
7. THE StudyReport.charts SHALL 为 JSONField, 存储所有渲染过的图表的 chart_spec。

### Requirement 18: Custom Report(Sidebar 问答)

**User Story:** As a 研究者, I want 在分析页 sidebar 随时向 AI 提问并得到带图表带引用的答案, so that 我能深挖具体维度而不依赖预设报告。

#### Acceptance Criteria

1. THE 分析页 SHALL 在右侧固定 Custom Report sidebar,可输入任意自然语言问题。
2. WHEN 研究者提问, THE Analysis_Agent SHALL 通过 retriever 从 `SessionInsight + transcript chunks` 召回片段,并通过 function call 输出 `{answer_markdown, chart_spec, citations}`。
3. THE chart_spec SHALL 包含 `type ∈ {bar, line, pie}`, `title`, `x`, `y`, `unit`。
4. THE citations SHALL 为 `[{session_id, ts, quote, speaker}]` 列表。
5. THE Analysis_Agent SHALL 支持至少三个可调 function: `aggregate_tag(tag_name)` / `filter_sessions(criteria)` / `cite_quote(session_id, ts)`。
6. THE 前端 SHALL 用 Chart.js 或 ECharts 渲染 chart_spec。
7. WHEN 研究者点击某条 citation, THE System SHALL 跳转到对应 transcript 的时间戳位置。
8. THE CustomReportQuery 模型 SHALL 使用 `merism_custom_report_query` 作为 `db_table`, 含 FK 到 Study(可为 null 表示跨 study)、FK 到 User、`team_id`。
9. THE System SHALL 支持将单条问答"钉到看板"或"保存为洞察"。

### Requirement 19: 跨 Study 知识库(Explore)

**User Story:** As a 研究者或团队 leader, I want 在 `/research/knowledge` 对所有 study 的访谈内容提问, so that 我能做跨研究的趋势对比和历史检索。

#### Acceptance Criteria

1. THE `/research/knowledge` 页 SHALL 展示: 大输入框"问我任何事" / 提示例问列表 / filter(Study / Date / Persona) / 最近问答列表。
2. WHEN 研究者在 Knowledge 页提问, THE Analysis_Agent SHALL 以 `CustomReportQuery.study = null` 创建问答记录,检索范围覆盖该 team 下所有 study 的 SessionInsight + transcript。
3. THE 跨 study 的 citation SHALL 标明 `[study_name · session_id · timestamp]`。
4. THE 答案页布局 SHALL 与 Custom Report 一致(markdown + chart + citations)。
5. THE Knowledge 页顶部 SHALL 展示统计信息: "跨 N 个 study, M 场访谈"。

### Requirement 20: 外部服务栈约束

**User Story:** As a 平台运维者, I want 所有 LLM/TTS/STT/Vision 调用都走统一的包装层, so that 成本和 trace 可被集中观测。

#### Acceptance Criteria

1. THE System SHALL 使用 DeepSeek v3 / DeepSeek Reasoner 作为默认 LLM(通过切换 `merism.llm_gateway.client.get_client` 包装器的 `base_url`)。
2. THE System SHALL 使用 Qwen CosyVoice(流式)作为 TTS。
3. THE System SHALL 使用 Qwen Paraformer-realtime 作为 STT。
4. THE System SHALL 使用 Qwen-VL-Max 作为视觉理解模型。
5. THE System SHALL 使用 `merism.services.storage`(boto3 + S3/MinIO)存储录音/录像/刺激物/附件。
6. THE System SHALL NOT 在默认安装中依赖 DashScope 特定地理区域的 endpoint(按 ADR 0002 延后决策)。
7. THE System SHALL NOT 引入 Node.js plugin-server 做行为触发(按 ADR 0001,行为触发走 Celery beat + HogQL scanner)。

### Requirement 21: 数据模型与 db_table 前缀

**User Story:** As a 平台维护者, I want 所有 Merism 表统一前缀且带 team_id, so that 多租户隔离可被 SQL 层直接审计。

#### Acceptance Criteria

1. THE 所有 Merism 相关 Django 模型 SHALL 设置 `class Meta: db_table = "merism_xxx"`。
2. THE 所有租户数据模型 SHALL 包含 `team_id`(作为 FK 到 merism.Team 或 BigIntegerField,取决于是否单 DB)。
3. THE 本计划 SHALL NOT 主动删除以下 Phase 0 遗留表: `StudyGoal`, `StudyTransition`, conductor policies 相关持久化。
4. THE 本计划 SHALL NOT 在代码路径中引用 `StudyGoal` 多 goal flat list; 统一使用 `Study.research_goal` 单文本字段。
5. THE 本计划 SHALL NOT 使用 Conductor policies(coverage / engagement / off_topic)—— 100+ 真实访谈后再评估需要哪个。

### Requirement 22: 权限与 Team 隔离

**User Story:** As a 平台安全负责人, I want 所有数据按 team 严格隔离, so that 不同租户的研究数据互不可见。

#### Acceptance Criteria

1. THE 所有 Merism API viewset SHALL 通过 `self.context["get_team"]()` 获取当前 team,并用 `team_id` 过滤 queryset。
2. THE API viewset SHALL 声明 request/response schema(使用 `@validated_request` 或 `@extend_schema`)。
3. WHERE 当前用户不属于 Study.team, THE API SHALL 返回 404(不暴露存在性)。
4. THE 公开访谈链接 `/i/:slug` SHALL 通过 slug 查找 Study,不需要登录,但不得暴露内部 study id 或 team id。
5. THE Preview_Mode 的鉴权 SHALL 通过 `self.context["get_team"]()` 校验团队成员身份,不依赖外部 token,不在受访者公开路径上挂任何 preview 参数。

### Requirement 23: 成本观测

**User Story:** As a 产品负责人, I want 每场访谈的 LLM / TTS / STT / Vision 成本被单独记录, so that 我能追踪单位经济并对高成本 study 告警。

#### Acceptance Criteria

1. THE 所有 LLM 调用 SHALL 通过 `merism.llm_gateway.client.get_client` 包装器,自带 trace 和成本统计。
2. THE InterviewSession SHALL 记录该次访谈的累计 cost_cents(可后台聚合,不要求实时在前端展示)。
3. WHILE 单场 InterviewSession 成本超过预设阈值(默认 $10), THE System SHALL 写一条 `InboxItem.kind=cost_alert`(或 `study_stuck` 占位)给 study owner 通知。

### Requirement 24: 前端设计系统边界

**User Story:** As a 前端贡献者, I want 所有 Merism 新 surface 统一从 `~/lib/merism` 引用 primitives, so that 样式和交互一致、未来换设计系统成本可控。

#### Acceptance Criteria

1. THE 所有新 Merism 前端代码(Ask / Interview Room / Wizard / Inbox / Repository / Decisions / Analysis / Knowledge) SHALL 从 `~/lib/merism` 引用 primitives / patterns / tokens。
2. THE 所有新 Merism 前端代码 SHALL NOT 引入 LemonUI 组件。
3. WHERE 存在 kea logic 文件, THE 业务逻辑 SHALL 写入 kea logic(不得用 React hooks 替代)。
4. THE 前端 CSS SHALL 使用 Tailwind 工具类,不使用内联 style。

### Requirement 25: 测试策略

**User Story:** As a 开发者, I want 按 Merism 的双 pytest 入口组织测试, so that 我能快速跑轻量单测也能跑完整 ORM 测试。

#### Acceptance Criteria

1. THE 与 Django DB 无关的单测 SHALL 通过 `pytest -c products/studies/pytest.ini` 运行(轻量/smoke 入口)。
2. THE 需要 ORM 的测试 SHALL 通过 `pytest -c products/studies/pytest.orm.ini` + `DJANGO_SETTINGS_MODULE=products.studies.test_settings_orm` 运行。
3. THE 对同一逻辑的多种输入变体 SHALL 使用 `parameterized` 库参数化,不手写重复 assert。
4. THE 对 Outline_Review_Agent、Interview_Moderator_Agent、Analysis_Agent 的 LLM 交互 SHALL 通过 mock `merism.llm_gateway.client.get_client` 的响应测试,不发真实请求。
5. THE 对 AI agent 的 prompt 构造 SHALL 有 snapshot 测试,保证 research_goal / current_question / stimulus / vision_context 正确注入。

### Requirement 26: 非目标(明确不做)

**User Story:** As a 项目 leader, I want 明确写下这次不做什么, so that scope 不被悄悄扩张。

#### Acceptance Criteria

1. THE 本计划 SHALL NOT 实现独立的 conductor 3 层架构(macro/meso/micro 分离)—— 决策逻辑合并在单次 LLM function call 中。
2. THE 本计划 SHALL NOT 实现 coverage / engagement / off_topic policies —— 等有 100+ 真实访谈后再评估。
3. THE 本计划 SHALL NOT 实现 StudyGoal 多目标 flat list —— 只用 `Study.research_goal` 单文本字段。
4. THE 本计划 SHALL NOT 实现 StudyTransition 状态机转移审计 —— 直接改 `Study.status`。
5. THE 本计划 SHALL NOT 把分析维度(tag schema)做成独立 UI —— 完全由 AI 自动推导。
6. THE 本计划 SHALL NOT 集成 Email / SMS 作为 MVP 招募渠道(Resend / Twilio 延后)。

### Requirement 27: 埋点与可观测

**User Story:** As a 产品经理, I want 关键用户行为被埋点, so that 我能分析转化漏斗和功能使用率。

#### Acceptance Criteria

1. THE System SHALL 在以下节点埋点: study_created / outline_finalized / recruit_link_generated / participation_started / session_completed / insight_generated / study_report_generated / custom_report_query_submitted。
2. THE 在 Celery task 内部的埋点 SHALL 使用 `merism.memai.capture.scoped_capture`(不使用 `structlog`/Langfuse 直接埋点)。
3. THE 每个埋点事件 SHALL 包含 `team_id`, `study_id`(如适用), `user_id`(如适用)。
