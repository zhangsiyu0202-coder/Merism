 # Merism — 产品规范

  > **单一事实源**。**2026-05-09 reset** 后取代已删除的 4 份文档（`PRODUCT_TRANSFORMATION_PLAN.md` / `USER_FLOWS.md` / `CONDUCTOR_DESIGN.md` / `ASK_MERISM_DESIGN.md`）。
  > 所有设计决策、API 约定、UI 规范在这里收敛。其他规划类文档（PLAN / RUNBOOK / ADR / EXECUTION_PLAN）跟本文不一致时以本文为准。
  > 修改本文件必须在 PR 描述说明"跟原文哪里不一样、为什么改"；设计讨论先更新本文件，再动代码。

  ## 文档导航

  | § | 内容 |
  |---|---|
  | [§0](#0-产品一句话定义) | 产品一句话定义 |
  | [§1](#1-北极星research-goal-贯穿全程) | 北极星：Research Goal 贯穿全程 |
  | [§2](#2-用户流程) | 用户流程（研究者 / 受访者） |
  | [§3](#3-界面规范) | 界面规范（创建 / tabs / 提纲审查 / 受访者房间 / 分析页 / 知识库） |
  | [§4](#4-数据模型) | 数据模型 |
  | [§5](#5-ai-agent-架构3-个) | AI Agent 架构（3 个） |
  | [§6](#6-外部服务栈) | 外部服务栈 |
  | [§7](#7-phase-0-可复用的不要重写) | Phase 0 可复用的（不要重写） |
  | [§8](#8-分阶段实施) | 分阶段实施 |
  | [§9](#9-非目标不要扩张进来) | 非目标（不要扩张） |
  | [§10](#10-开放问题需后续回答) | 开放问题 |

  ---

  ## 0. 产品一句话定义

  **Merism 是一个 AI 驱动的用户研究平台**：研究者写一个研究目标 → AI 帮他拟访谈提纲并审查修改 → 通过 CowAgent 群发或公开链接招募受访者 → 受访者进入房间与 AI
  主持人进行音频/视频访谈 → AI 自动做个体分析与群体综合，生成带引用、带可视化的结构化报告 → 多个研究沉淀成跨库问答知识库。

  ---

  ## 1. 北极星：Research Goal 贯穿全程

  这是唯一的"核心"。创建 study 的第一步就让用户输入 research goal（例："调研 18–25 岁用户对 XX 零食的口味满意度"），此后的每个 AI 环节都以它为锚点：

  | 环节 | research_goal 如何参与 |
  |---|---|
  | 提纲生成 | AI 按 goal 生成问题 sections |
  | 提纲审查 | AI 检查每个问题是否服务 goal |
  | 访谈主持 | AI 系统 prompt 注入 goal，避免跑题 |
  | 个体分析 | AI 按 goal 抽取 highlights + tag 维度 |
  | 群体综合 | 群体 finding 按 goal 分类 |
  | Custom Report | 用户提问时，AI 先匹配 goal context |
  | 知识库 | 跨研究检索时按 goal 相似度排序 |

  **分析维度不做独立 UI**。tag / dimension schema 由 AI 从 `research_goal + outline_questions` 自动推导（例：goal 是满意度调研 → 自动生成 `sentiment` / `specific_pain_points` /
  `recommendation_likelihood` 等维度）。用户只需写好 goal 和提纲。

  ---

  ## 2. 用户流程

  ### 2.1 研究者流程

  [1] 创建 study
        · 唯一必填：research_goal（一句话）
        · 可选：研究背景、假设、成功指标
        ↓
  [2] 设置 screener（受访者筛选条件）
        · 自然语言描述 + AI 辅助转结构化条件
        · 例："过去 30 天买过零食的 18–25 岁在校生"
        ↓
  [3] 编辑提纲
        · AI 基于 goal 生成初稿
        · 可拖拽排序 / 编辑 / 增删问题
        · 每题单独配置：是否追问、追问深度（0/1/2/3）、是否必答
        · 可关联刺激物（某题展示时显示 xx 图）
        ↓
  [4] AI 审查提纲（对话式）
        · 研究者点"让 AI 审查"→ 右侧打开 chat
        · AI 指出：隐私问题 / 顺序不合理 / 引导性表达 / 结构缺漏
        · 研究者可辩护 / 接受 / 指示 AI 改某处
        · 最终 AI 把修改后的提纲写回主界面
        ↓
  [5] 上传刺激物（可选，全 study 级或 per-question 级）
        · 图片 / 视频 / 文字段落 / 外链
        ↓
  [6] 生成公开访谈链接 + 设置招募
        · 链接自动生成（提纲 finalize 后）
        · 招募渠道：CowAgent（飞书/企微/QQ 已集成）+ 手动分发链接
        ↓
  [7] 预先进入「受访者房间」自测
        · 以受访者身份走一遍流程
        · 不写入真实 session、不扣配额
        ↓
  [8] 正式开始收集
        · 研究者 dashboard 看进度、已完成访谈列表、高亮 quote feed
        ↓
  [9] 进入分析页
        · 主区：默认结构化报告（Exec Summary + 定量/定性对照 + Insight nuggets）
        · 侧栏：Custom Report —— 用户提问，AI 生成带图表的答案
        ↓
  [10] 研究沉淀到跨库知识库
        · 自动被 Explore 页面检索到

  ### 2.2 受访者流程

  [1] 打开邀请链接 /i/:slug
        ↓
  [2] Consent 页：告知将被 AI 主持 + 录音/录像同意 + 隐私条款
        ↓
  [3] Screener 快速筛（1–3 道）
        · 不符合 → 感谢退出
        · 符合 → 继续
        ↓
  [4] 准备页：选择「音频」或「视频」（如 study 允许两种）+ 测麦 / 测像头
        ↓
  [5] 进入房间，AI 开场
        · TTS 语音 + 同步字幕
        · 按提纲依次提问
        · 每题根据 followup_depth 决定追问几轮
        ↓
  [6] 完成访谈
        · 感谢页 + 可选反馈

  ---

  ## 3. 界面规范

  ### 3.1 Create Study Modal

  单一输入框优先：

  ┌─────────────────────────────────────────────────┐
  │  创建新研究                              [×]    │
  ├─────────────────────────────────────────────────┤
  │                                                 │
  │  你这次要研究什么？                              │
  │                                                 │
  │  [____________________________________________] │
  │   例：调研 18-25 岁用户对 XX 零食的口味满意度   │
  │                                                 │
  │  ─ 可选：补充背景 ────────────────────────────  │
  │  [▸ 添加假设 / 成功指标 / 研究背景]              │
  │                                                 │
  │              [取消]  [下一步 →]                  │
  └─────────────────────────────────────────────────┘

  点 `[下一步]` → 创建 `Study(research_goal=...)` → 跳到 Study 详情页 Brief tab。

  ### 3.2 Study 详情 tabs

  Brief  |  Outline  |  Screener  |  Stimuli  |  Recruit  |  Analysis  |  Knowledge  |  Settings

  - **Brief**：研究目标、背景、假设；dashboard（进度、完成数、完成率）
  - **Outline**：提纲编辑器 + AI 审查对话（§3.3）
  - **Screener**：筛选条件编辑
  - **Stimuli**：刺激物上传 / 管理（§3.4）
  - **Recruit**：生成公开链接 + CowAgent 群发配置 + 状态监控
  - **Analysis**：主报告 + Custom Report（§3.6）
  - **Knowledge**：本 study 内问答（是跨库 Knowledge 的子集）
  - **Settings**：权限、归档、删除、导出

  ### 3.3 提纲编辑器 + AI 审查

  布局：主区可编辑提纲 + 顶部 `[✨ 让 AI 审查]` 按钮；点击 → 右侧抽屉打开 chat。

  **提纲结构**：

  Section 1: Warmup (2 min)
    Q1. 简单介绍下你的零食消费习惯？
        ┌ 追问：深度 1 / 必答 ✓ / 刺激物：无
        └ 探针方向：频率 / 购买渠道

  Section 2: Core (10 min)
    Q2. 你第一次看到这款零食时的感受？
        ┌ 追问：深度 2 / 必答 ✓ / 刺激物：img-001 (包装正面)
        └ 探针方向：包装设计 / 价格预期 / 购买意愿
    ...

  Section 3: Closing (3 min)
    ...

  每个 Q 卡片含：问题文本、追问深度选择、必答开关、刺激物关联、探针方向列表。Q 可拖拽；section 可折叠。

  **AI 审查 chat**（右侧抽屉）：

  ╭─ AI 审查 ────────────────────────────────╮
  │ 你：帮我看看这个提纲                     │
  │                                          │
  │ AI: 我看完了，有 3 个建议：               │
  │  1. Q3 "你年收入多少" 属于敏感 PII，      │
  │     如果不是必要变量，建议改成区间选择    │
  │  2. Section 2 全是 open 问题，建议插入 1  │
  │     道 Likert 量表（避免受访者疲劳）      │
  │  3. Q7 包含引导："你一定会推荐给朋友吗?"  │
  │     建议改成中性："你会怎么向朋友描述？"   │
  │                                          │
  │ [接受 1]  [接受 2]  [接受 3]  [全部接受] │
  │                                          │
  │ 你：Q3 必须问，但我可以接受区间           │
  │                                          │
  │ AI: 好，我把 Q3 改成 5 档收入区间选择。   │
  │     [应用修改]                           │
  ╰──────────────────────────────────────────╯

  研究者确认 `[应用修改]` → AI 直接把新版提纲写回主区，研究者可二次微调。

  ### 3.4 Stimuli 管理

  全 study 级的素材库：

  [+ 上传]  支持：jpg/png/gif · mp4/webm · pdf · 文字块 · 外链

  ┌─── img-001 · snack_front.jpg · 240KB ─────────┐
  │ [缩略图] 包装正面                              │
  │ 关联问题：Q2, Q5                                │
  │ [预览] [编辑] [删除]                           │
  └────────────────────────────────────────────────┘

  ┌─── vid-001 · unboxing.mp4 · 12.4MB ───────────┐
  │ [缩略图] 开箱视频（0:45）                      │
  │ 关联问题：Q6                                    │
  └────────────────────────────────────────────────┘

  提纲编辑器里每个问题可关联 1 个或多个 `stimulus_id`。访谈时，某题 active → 左 2/3 展示区覆盖展示对应 stimulus。

  ### 3.5 受访者房间 ⭐ 核心

  **布局**（左 2/3 / 右 1/3）：

  ┌─ 顶部导航（白色固定，中央 Logo） ─────────────────────────────┐
  ├──────────────────────────────────────────────┬──────────────┤
  │                                              │              │
  │  左 2/3 —— AI + 摄像头 + 刺激物              │  右 1/3 ——  │
  │                                              │  对话框      │
  │  ┌──────────────────────────────────────┐   │              │
  │  │ AI INTERVIEWER (小灰标签)            │   │  • 实时语音  │
  │  │ 这是 AI 当前的问题文本，较高行高     │   │    转写字幕  │
  │  │                                      │   │  • AI 字幕   │
  │  │          ●  Begin response           │   │    同步展示  │
  │  │              (紫色大按钮 + 摄像图标) │   │  • 上传图片/ │
  │  │                                      │   │    视频按钮  │
  │  │ ┌──────────────────────────────────┐ │   │              │
  │  │ │  [摄像头预览 / 刺激物展示区]      │ │   │  [上传区]    │
  │  │ │                                  │ │   │              │
  │  │ │  · 音频模式：占位 + 波形         │ │   │  [消息流]    │
  │  │ │  · 视频模式：用户摄像头画面      │ │   │              │
  │  │ │  · 当前题关联 stimulus 时：      │ │   │              │
  │  │ │    覆盖展示该刺激物              │ │   │              │
  │  │ └──────────────────────────────────┘ │   │              │
  │  └──────────────────────────────────────┘   │              │
  └──────────────────────────────────────────────┴──────────────┘
  背景 bg-gray-100  ·  h-screen

  **音频 vs 视频模式差异**：

  | 维度 | 音频模式 | 视频模式 |
  |---|---|---|
  | 摄像头 | 关闭；预览框显示占位 + 波形 | 开启；预览框实时显示用户画面 |
  | Vision | 不启用 | 每 10s 抽帧喂给 Qwen-VL，AI 能看到表情/手势/展示物 |
  | 录制 | 仅音频 → S3 | 音频 + 视频分轨 → S3 |
  | 受访者完成率 | 高（~80%） | 低（~50–70%，摄像头摩擦） |
  | 成本 | ~$2–3/场 | ~$5–8/场（加 vision token） |

  **刺激物交互**：

  - 某题 active 且关联 stimulus → 预览框覆盖显示刺激物
  - 用户可点 `[✕ 关闭]` 切回摄像头预览（视频模式）或波形（音频模式）
  - AI prompt 注入："受访者现在正在看 stimulus-XXX（描述：...）"

  **右侧对话框**：

  - 实时语音转写（Qwen Paraformer STT 流式）
  - AI 字幕（跟 TTS 音频同步出字）
  - 附件上传：图片 / 视频 / PDF → S3 → 喂给 Qwen-VL → AI 基于附件内容追问
  - 文字输入（退化选项，网络不好或不想开麦时）

  **自测模式**：

  - URL `/i/:slug?preview=1&token=xxx`
  - 不创建真实 Participation
  - 不写入 Session
  - 不扣配额
  - 右下角显示"自测模式"橙色角标

  ### 3.6 分析页

  **主区（Mixed-Methods Insights Dashboard）**：

  ┌─────────────────────────────────────────────────────────────┐
  │ [💬 图标] Executive Summary                                  │
  │ 本研究共访谈 47 人，核心发现：XXX...                          │
  │ （无边框，灰底，结论先行）                                    │
  ├─────────────────────────────────────────────────────────────┤
  │                                                             │
  │ ┌─── 定量面板 (5/12) ────┐  ┌─── 定性面板 (7/12) ───────┐ │
  │ │ [Guide Question 框]    │  │ [breadcrumb]               │ │
  │ │ Q: 你觉得这个零食最    │  │ 详细解释性富文本，关键     │ │
  │ │    大的特点是什么？    │  │ 词 下划线高亮...         │ │
  │ │                        │  │                            │ │
  │ │   ▃ ▃                  │  │ ┌─ quote 卡 ────────────┐ │ │
  │ │   █ ▃ ▃                │  │ │ [▶] "我觉得特别脆"     │ │ │
  │ │   █ █ █ ▃              │  │ │      — Sarah · 03:42   │ │ │
  │ │   █ █ █ █              │  │ └────────────────────────┘ │ │
  │ │   脆  甜  咸  香       │  │ ┌─ quote 卡 ────────────┐ │ │
  │ │  (最高柱蓝色，其余灰)  │  │ │ [▶] "甜度刚好"         │ │ │
  │ └────────────────────────┘  │ │      — Mark · 08:15    │ │ │
  │                             │ └────────────────────────┘ │ │
  │                             └────────────────────────────┘ │
  ├─────────────────────────────────────────────────────────────┤
  │                                                             │
  │ Insight nuggets                                             │
  │ ┌──────────┐ ┌──────────┐ ┌──────────┐                    │
  │ │ [icon]   │ │ [icon]   │ │ [icon]   │                    │
  │ │ 价格敏感 │ │ 包装视觉 │ │ 分享意愿 │                    │
  │ │ 73% 受访 │ │ 60% 喜欢 │ │ 42% 会推 │                    │
  │ │ 者提到…  │ │ 当前设计 │ │ 荐给朋友 │                    │
  │ └──────────┘ └──────────┘ └──────────┘                    │
  └─────────────────────────────────────────────────────────────┘

  **右侧 sidebar —— Custom Report**：

  ╭─ Custom Report ──────────────────╮
  │                                  │
  │ 你：什么原因导致用户不推荐？      │
  │                                  │
  │ AI: 综合 47 场访谈，3 个主因：    │
  │                                  │
  │   [柱状图：3 个原因 × 提及人数]  │
  │                                  │
  │ 1. 价格过高 (18/47 = 38%)        │
  │    · "比同类贵 30%" — Tom [1]    │
  │    · "学生党买不起" — Lily [2]   │
  │                                  │
  │ 2. 口味太甜 (14/47 = 30%)        │
  │    · ...                          │
  │                                  │
  │ 3. 包装难拆 (9/47 = 19%)         │
  │    · ...                          │
  │                                  │
  │ [📌 钉到看板]  [💾 保存为洞察]   │
  │                                  │
  │ ─────────────────────────────    │
  │                                  │
  │ 你：再分析下性别差异？            │
  │ ...                              │
  ╰──────────────────────────────────╯

  **Custom Report 技术要点**：

  - 用户提问 → AI 决定要不要画图 → 画什么图（柱 / 折线 / 饼）→ 用哪些数据 → 生成答案
  - AI 通过 function call 返回结构化结果：

  ```json
  {
    "answer_markdown": "...",
    "chart": {
      "type": "bar",
      "title": "不推荐原因",
      "x": ["价格过高", "口味太甜", "包装难拆"],
      "y": [18, 14, 9],
      "unit": "人"
    },
    "citations": [
      {"session_id": "xxx", "ts": 342.5, "quote": "比同类贵 30%", "speaker": "Tom"}
    ]
  }

  - 前端用 Chart.js 或 ECharts 渲染；每条 citation 可点击跳转到 transcript 对应时间戳
  - LLM 可调用的 function：aggregate_tag(tag_name) / filter_sessions(criteria) / cite_quote(session_id, ts)

  3.7 知识库页（跨 study Explore）

  /research/knowledge

  ┌─────────────────────────────────────────────────────────┐
  │ ← 返回  |  Explore  (跨 47 个 study，3,214 场访谈)      │
  ├─────────────────────────────────────────────────────────┤
  │                                                         │
  │ 问我任何事                                               │
  │ [_____________________________________________]  [↵]   │
  │                                                         │
  │ 💡 你可能想问：                                          │
  │ · 用户为什么不续约？                                     │
  │ · 不同年龄段对 pricing 的反应？                          │
  │ · 去年 Q3 调研和今年 Q1 调研的差异？                     │
  │                                                         │
  │ ─── Filter ─────────────────────────────────────────── │
  │ [Study ▾]  [Date ▾]  [Persona ▾]                       │
  │                                                         │
  │ ─── 最近问答 ─────────────────────────────────────────  │
  │ · "产品定价反馈" (2 天前)                               │
  │ · "Onboarding 痛点" (5 天前)                            │
  └─────────────────────────────────────────────────────────┘

  提问后跳到同样 Custom Report 风格的答案页，但检索范围是所有 study，每条 citation 标明 [study_name · session_id · timestamp]。

  ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  4. 数据模型

  核心表（跟 Phase 0 已有的尽量兼容）：

  # 已有，基本保留
  Study:
      research_goal: TextField                # 唯一必填
      research_background: TextField
      hypothesis: TextField
      success_metrics: JSONField
      status: ChoiceField[draft, ready, recruiting, active, closed, archived]

  # 已有，扩展
  InterviewGuide:   # = "提纲"
      study: FK
      version: Int
      sections: JSONField  # [{id, title, questions: [...]}]
      # 每个 question 含：
      #   id, text, followup_depth (0-3), required, probe_directions[],
      #   linked_stimulus_ids[]

  # 新增
  Screener:
      study: FK
      questions: JSONField  # [{text, type: single|multi|range, options[]}]
      pass_logic: JSONField  # 通过条件

  Stimulus:
      study: FK
      kind: ChoiceField[image, video, text, pdf, link]
      content: JSONField  # { url, text, title, description }
      linked_question_ids: JSONField

  # 已有，基本保留
  Participation:
      study: FK
      slug: CharField
      source: ChoiceField[cowagent, public_link, ...]
      status: ChoiceField[invited, started, completed, dropped]
      is_preview: BooleanField  # 自测模式不写入正式数据

  InterviewSession:
      participation: FK
      mode: ChoiceField[audio, video]
      transcript: JSONField  # [{role, text, ts_start, ts_end}]
      audio_s3_key: CharField
      video_s3_key: CharField (null)
      vision_frames: JSONField  # video 模式采样帧，[{ts, vl_description}]

  # 已有
  SessionInsight:  # 个体分析
      session: FK
      summary: TextField
      highlights: JSONField  # [{text, ts_start, ts_end, importance}]
      tags: JSONField        # AI 抽取的分析维度值
      extracted_tasks: JSONField  # action items

  # 新增
  StudyReport:
      study: FK
      content: JSONField     # 结构化 schema：exec_summary / quant_panel / qual_panel / insight_nuggets
      charts: JSONField      # 所有渲染过的图
      generated_at: DateTimeField

  CustomReportQuery:  # 用户在 sidebar 提的问题
      study: FK              # null 表示跨 study（Knowledge）
      user: FK
      question: TextField
      answer_markdown: TextField
      chart_spec: JSONField
      citations: JSONField   # [{session_id, ts, quote, speaker}]
      created_at: DateTimeField

  已有但本计划不再需要的表（Phase 0 遗留，保留向后兼容，不主动删）：

  - StudyGoal（多 goal flat list）—— 我们只用单 Study.research_goal 文本字段
  - StudyTransition（状态机转移审计）—— 简化为直接改 Study.status
  - Conductor policies 相关持久化（decision_log / coverage / engagement）—— policies 全部移除

  ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  5. AI Agent 架构（3 个）

  5.1 Outline Review Agent

  触发：研究者点"让 AI 审查"按钮。
  形态：对话式（研究者可来回辩论）。
  输入：research_goal + 当前提纲 JSON + 研究者最新消息。

  输出 schema（function calling）：

  {
    "reply_markdown": "我看了下提纲，有 3 个建议...",
    "proposed_changes": [
      {"op": "modify_question", "question_id": "q3", "new_text": "..."},
      {"op": "insert_question", "after_id": "q5", "question": {...}},
      {"op": "remove_question", "question_id": "q7"}
    ],
    "awaiting_user_decision": true
  }

  研究者确认后，前端逐条 apply proposed_changes。

  Prompt 要点：

  - 审查维度：privacy（PII 问题）/ ordering（冷热度）/ structure（warmup→core→closing）/ bias（引导性、双重否定）/ 与 research_goal 对齐 / followup_depth 是否合理
  - 禁止代替决定：要问"你希望……？"而不是自己改

  5.2 Interview Moderator Agent

  触发：受访者进入房间。
  形态：流式 voice + text。

  循环（每个 user turn 后跑一次）：

  1. STT 产出 final transcript segment
  2. 更新 conversation state:
     - 当前在第几题
     - 该题已追问几次
     - 剩余追问预算 = followup_depth - 已追问
  3. 构造 system_prompt:
     - <research_goal>{...}</research_goal>
     - <current_question>{...}</current_question>
     - <current_stimulus>{...}</current_stimulus>  (如有)
     - <remaining_followups>{n}</remaining_followups>
     - <vision_context>{...}</vision_context>  (视频模式，最近一帧 VL 描述)
  4. LLM (DeepSeek) 流式生成下一句 + tool call:
     {
       "next_action": "followup" | "move_on" | "clarify" | "close",
       "next_question_id": "q5"  // 仅 move_on
     }
  5. 前端并行两路：
     · 文字 → Qwen CosyVoice 流式 TTS → 推音频给浏览器
     · 文字 → 推字幕给对话框
  6. 用户回答 → STT → 回到 1

  关键规则：

  - 受访者的每个回答，AI 用 1 次 LLM 调用同时决定"说什么" + "下一步做什么"（function call 合并，不调两次）
  - 预算耗尽（remaining_followups == 0）强制 move_on
  - 全部题问完 + closing section 过 → next_action=close → 受访者看到感谢页

  不做：

  - 不做独立的 macro/meso 决策层（decision 逻辑塞进同一个 LLM call 的 function call）
  - 不做独立 policies（coverage / engagement / off_topic）—— 等有 100+ 真实访谈后再看需要哪个

  5.3 Analysis Agent

  (A) 访谈结束后个体分析（Celery task）：

  输入：InterviewSession.transcript + research_goal + outline
  调用：一次 LLM（DeepSeek，可用 reasoner 版本）
  输出：SessionInsight
    - summary: 3-5 句
    - highlights: 3-8 条带时间戳
    - tags: { dimension_name: value, ... }   （维度从 goal + outline 自动推导）
    - extracted_tasks: [{title, category, priority, evidence_quote_id}]

  (B) 群体分析 + Custom Report（用户触发）：

  - 默认 StudyReport：收集够 N 场 session 后（或手动触发），AI 汇总所有 SessionInsight + 调整 tag 维度 → 产出 exec_summary + 定量 panel + 定性 panel + insight nuggets
  - Custom Report（sidebar 提问）：
    - retriever：基于问题 + research_goal 从 SessionInsight + transcript chunks 召回片段
    - generator：给 LLM 带 context，让它用 function call 输出 {answer, chart_spec, citations}
    - LLM 可调用的 function：
      - aggregate_tag(tag_name) 返回该 tag 在所有 session 的分布（画图用）
      - filter_sessions(criteria) 返回符合条件的 session_ids
      - cite_quote(session_id, ts) 返回原文片段

  ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  6. 外部服务栈

  ┌─────────────┬──────────────────────────────────────┬─────────────────────────────────────────────────────────────────────┬─────────────────────────────────┐
  │ 服务        │ 用途                                 │ 选型                                                                │ 理由                            │
  ├─────────────┼──────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┼─────────────────────────────────┤
  │ LLM         │ 所有文本生成 / 推理                  │ DeepSeek v3 / DeepSeek Reasoner                                     │ 成本低、中文好、可私有化        │
  ├─────────────┼──────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┼─────────────────────────────────┤
  │ TTS         │ AI 语音输出                          │ Qwen CosyVoice（流式）                                              │ 中文自然、可 barge-in、费用可控 │
  ├─────────────┼──────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┼─────────────────────────────────┤
  │ STT         │ 受访者语音转写                       │ Qwen Paraformer-realtime                                            │ 流式低延迟、中英混合支持        │
  ├─────────────┼──────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┼─────────────────────────────────┤
  │ Vision      │ 视频模式看摄像头 + 用户上传图片/视频 │ Qwen-VL-Max                                                         │ 同 Qwen 全栈，账号统一          │
  ├─────────────┼──────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┼─────────────────────────────────┤
  │ 对象存储    │ 录音 / 录像 / 刺激物 / 附件          │ PostHog object_storage（S3 抽象）                                   │ 复用已有                        │
  ├─────────────┼──────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┼─────────────────────────────────┤
  │ 招募        │ 飞书 / 企微 / QQ 群发                │ CowAgent adapters（已集成在 products/studies/backend/recruitment/） │ Phase 0 已完成                  │
  ├─────────────┼──────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┼─────────────────────────────────┤
  │ Email / SMS │ 邀请备用渠道                         │ Resend / Twilio（可延后）                                           │ 非 MVP                          │
  └─────────────┴──────────────────────────────────────┴─────────────────────────────────────────────────────────────────────┴─────────────────────────────────┘

  所有 LLM 调用通过 posthoganalytics.ai.openai 包装（自带 trace + 成本统计）；DeepSeek 兼容 OpenAI API 直接切换 base_url。

  ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  7. Phase 0 可复用的（不要重写）

  直接用

  ┌─────────────────────────────────────────────────────────────────────────────────────────────────┬─────────────────────────────────────────────┬──────────────┐
  │ 模块                                                                                            │ 路径                                        │ 用途         │
  ├─────────────────────────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────┼──────────────┤
  │ Study / InterviewGuide / Participation / InterviewSession / SessionInsight / StudyReport models │ products/studies/backend/models.py          │ 数据模型基座 │
  ├─────────────────────────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────┼──────────────┤
  │ StudyViewSet + actions (launch/close/generate_guide/suggest_questions)                          │ products/studies/backend/api.py             │ API 骨架     │
  ├─────────────────────────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────┼──────────────┤
  │ Guide generator                                                                                 │ products/studies/backend/guide_generator.py │ 生成提纲初稿 │
  ├─────────────────────────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────┼──────────────┤
  │ Session insight / aggregate synthesis                                                           │ products/studies/backend/analysis.py        │
  └─────────────────────────────────────────────────────────────────────────────────────────────────┴─────────────────────────────────────────────┴──────────────┘