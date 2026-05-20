# Design Document

## Overview

Merism 平台的技术设计。本文档基于 `requirements.md` 和 `standalone/PRODUCT.md`,给出数据模型、API 表面、AI agent 实现、前端架构、集成点的细化方案。

设计原则:
- **复用 Phase 0 已有骨架**: `products/studies/backend/` 下的 models / api / guide_generator / analysis 作为基座,本设计是增量扩展
- **单次 LLM 调用决策**: Interview_Moderator_Agent 不拆分 macro/meso/micro,合并在一次 function-calling
- **严格 Team 隔离**: 所有 queryset 必须经 `team_id` 过滤,不信任任何外部 id
- **LLM 统一走 merism gateway**: `merism.llm_gateway.client.get_client` + DeepSeek 兼容 OpenAI API 切 `base_url`
- **前端 kea-first**: 业务逻辑进 kea logic,React 组件只做渲染
- **Merism 设计系统统一入口**: 所有新 surface 从 `~/lib/merism` 导入

## Architecture

### 高层分层

```
┌─────────────────────────────────────────────────────────────────┐
│ Frontend (React + Kea)                                           │
│  · Create / Study Tabs / Outline Editor / Interview Room /      │
│    Analysis Page / Knowledge Explore                             │
│  · Primitives from ~/lib/merism                                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ REST + SSE/WebSocket
┌───────────────────────────▼─────────────────────────────────────┐
│ Django Backend (products/studies/backend/)                       │
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────┐ │
│  │ StudyViewSet    │  │ InterviewSession │  │ AnalysisViewSet│ │
│  │ OutlineViewSet  │  │ ViewSet (SSE)    │  │ CustomReport   │ │
│  │ ScreenerViewSet │  │                  │  │ KnowledgeView  │ │
│  │ StimulusViewSet │  │                  │  │                │ │
│  │ RecruitViewSet  │  │                  │  │                │ │
│  └────────┬────────┘  └────────┬─────────┘  └────────┬───────┘ │
│           │                    │                     │          │
│  ┌────────▼────────────────────▼─────────────────────▼──────┐  │
│  │ Services Layer                                            │  │
│  │  · OutlineReviewService · InterviewModeratorService ·     │  │
│  │    AnalysisService · CustomReportService · GuideGenerator│  │
│  └───────────────────────────┬───────────────────────────────┘  │
│                              │                                   │
│  ┌──────────────┐ ┌──────────▼──────────┐ ┌──────────────────┐ │
│  │ Celery Tasks │ │ LLM Client Wrapper  │ │ Recruitment      │ │
│  │ analyze_     │ │ merism.llm_gateway. │ │ CowAgent adapters│ │
│  │ session,     │ │ client.get_client → │ │ (feishu/wecom/qq │ │
│  │ generate_    │ │ DeepSeek / Qwen     │ │  /email)         │ │
│  │ study_report │ │                     │ │                  │ │
│  └──────────────┘ └──────────┬──────────┘ └──────────────────┘ │
└─────────────────────────────┼───────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
    ┌──────────────────┐            ┌─────────────────────┐
    │ Postgres         │            │ External Services   │
    │ (merism_* tables)│            │ · DeepSeek (LLM)    │
    │                  │            │ · Qwen CosyVoice(TTS)│
    │ Object Storage   │            │ · Qwen Paraformer   │
    │ (audio/video/    │            │   (STT)             │
    │  stimuli/attach) │            │ · Qwen-VL-Max       │
    └──────────────────┘            └─────────────────────┘
```

### 请求路径概览

| 交互 | 链路 |
|---|---|
| 创建 study | `POST /api/projects/:team_id/studies/` → StudyViewSet → Study(merism_study) |
| 生成提纲初稿 | `POST /studies/:id/generate_guide/` → GuideGenerator → LLM → InterviewGuide v1 |
| AI 审查提纲 | `POST /studies/:id/review_outline/` (SSE) → OutlineReviewService → LLM(function call) → proposed_changes 流式回推 |
| 应用 proposed_changes | `POST /studies/:id/apply_outline_changes/` → InterviewGuide v+1 |
| 访谈进行中每轮 | 浏览器音频 → WS → STT(流式) → ModeratorService → LLM(function call, 流式) → TTS 流式回浏览器 + 字幕 SSE |
| 访谈结束分析 | session.complete() → Celery `analyze_session` → Analysis_Agent → SessionInsight |
| 群体报告 | `POST /studies/:id/generate_report/` → Celery `generate_study_report` → StudyReport |
| Custom Report 提问 | `POST /studies/:id/custom_reports/` → CustomReportService → retriever + LLM(function call) → 结果持久化 |
| Knowledge 跨 study 提问 | `POST /knowledge/ask/` → CustomReportService(study=null) |

## Data Model

所有模型 `class Meta: db_table = "merism_<name>"`。所有租户数据模型都带 `team_id`(FK 到 `merism.Team`)。

### 复用/扩展的已有模型

> 这些模型在 `products/studies/backend/models.py` 已存在,只列出本设计涉及的字段变更。

**Study** (merism_study)
```python
team = models.ForeignKey("merism.Team", ...)
research_goal = models.TextField()                       # 唯一必填
research_background = models.TextField(blank=True, default="")
hypothesis = models.TextField(blank=True, default="")
success_metrics = models.JSONField(default=dict, blank=True)
status = models.CharField(
    max_length=32,
    choices=[("draft","draft"),("ready","ready"),("recruiting","recruiting"),
             ("active","active"),("closed","closed"),("archived","archived")],
    default="draft",
)
slug = models.CharField(max_length=64, unique=True)      # 用于 /i/:slug
owner = models.ForeignKey("django.contrib.auth.User", ...)
created_at / updated_at
```

**InterviewGuide** (merism_interview_guide)
```python
study = FK(Study)
team = FK(Team)
version = models.PositiveIntegerField()
sections = models.JSONField()  # see schema below
is_current = models.BooleanField(default=False)  # 标记当前激活版本
created_at
```

sections JSON schema:
```json
[
  {
    "id": "s1",
    "title": "Warmup",
    "duration_min": 2,
    "questions": [
      {
        "id": "q1",
        "text": "...",
        "followup_depth": 1,
        "required": true,
        "probe_directions": ["频率", "购买渠道"],
        "linked_stimulus_ids": []
      }
    ]
  }
]
```

**Participation** (merism_participation) — 扩展 `is_preview`
```python
is_preview = models.BooleanField(default=False)  # self-preview 模式不写真实数据
```

**InterviewSession** (merism_interview_session) — 扩展 mode / vision_frames
```python
mode = models.CharField(max_length=16, choices=[("audio","audio"),("video","video")])
transcript = models.JSONField(default=list)    # [{role, text, ts_start, ts_end}]
audio_s3_key = models.CharField(max_length=255, blank=True, default="")
# audio 模式恒为空(不存音频);字段保留, 预留未来需要时复用
video_s3_key = models.CharField(max_length=255, blank=True, default="")
# 仅 video 模式写入
vision_frames = models.JSONField(default=list) # [{ts, vl_description}]  仅 video 模式累积
cost_cents = models.PositiveIntegerField(default=0)  # 累计 LLM/TTS/STT/Vision 成本
```

### 新增模型

**Screener** (merism_screener)
```python
team = FK(Team)
study = FK(Study, related_name="screener")  # OneToOne 行为:通过 select_related
questions = models.JSONField(default=list)
# [{id, text, type: single|multi|range, options: [...]}]
pass_logic = models.JSONField(default=dict)
# {"all": [{"q_id": "q1", "op": "in", "value": ["18-25"]}, ...]} DSL
created_at / updated_at
```

**Stimulus** (merism_stimulus)
```python
team = FK(Team)
study = FK(Study, related_name="stimuli")
kind = models.CharField(max_length=16,
    choices=[("image","image"),("video","video"),("text","text"),("pdf","pdf"),("link","link")])
content = models.JSONField(default=dict)  # {url, text, title, description}
linked_question_ids = models.JSONField(default=list)
created_at
```

**StudyReport** (merism_study_report)
```python
team = FK(Team)
study = FK(Study, related_name="reports")
content = models.JSONField()
# {exec_summary, quant_panel: [...], qual_panel: [...], insight_nuggets: [...]}
charts = models.JSONField(default=list)
generated_at = models.DateTimeField(auto_now_add=True)
generated_by = FK("django.contrib.auth.User", null=True)
```

**CustomReportQuery** (merism_custom_report_query)
```python
team = FK(Team)
study = FK(Study, null=True, blank=True)  # null 表示跨 study (Knowledge)
user = FK("django.contrib.auth.User")
question = models.TextField()
answer_markdown = models.TextField()
chart_spec = models.JSONField(null=True, blank=True)
citations = models.JSONField(default=list)
# [{session_id, ts, quote, speaker, study_id, study_name}]
is_pinned = models.BooleanField(default=False)
is_saved_insight = models.BooleanField(default=False)
created_at
```

**SessionInsight** (merism_session_insight) — 已有,字段澄清
```python
session = FK(InterviewSession)
team = FK(Team)
summary = models.TextField()
highlights = models.JSONField(default=list)
# [{text, ts_start, ts_end, importance}]
tags = models.JSONField(default=dict)
# {dimension_name: value}  维度由 AI 从 research_goal + outline 推导
extracted_tasks = models.JSONField(default=list)
# [{title, category, priority, evidence_quote_id}]
generated_at
```

### 索引

| 表 | 索引 |
|---|---|
| merism_study | `(team_id, status)`, `slug (unique)` |
| merism_interview_guide | `(study_id, is_current)`, `(study_id, version)` |
| merism_participation | `(study_id, status)`, `slug (unique)` |
| merism_interview_session | `(participation_id, -created_at)` |
| merism_session_insight | `(session_id unique)`, `(team_id, -generated_at)` |
| merism_custom_report_query | `(team_id, study_id, -created_at)`, `(team_id, user_id, -created_at)` |

## API Design

所有 viewset 继承 `ProductViewSet`,强制 team scoping。请求/响应 schema 由 DRF serializer + `@extend_schema` 声明,前端类型由 `hogli build:openapi` 生成。

### Study

| Method | Path | 说明 |
|---|---|---|
| POST | `/api/projects/:team_id/studies/` | 创建 study(只要 research_goal) |
| GET | `/api/projects/:team_id/studies/:id/` | 详情 |
| PATCH | `/api/projects/:team_id/studies/:id/` | 修改 |
| POST | `/api/projects/:team_id/studies/:id/launch/` | status → recruiting |
| POST | `/api/projects/:team_id/studies/:id/close/` | status → closed |
| POST | `/api/projects/:team_id/studies/:id/preview_session/` | 团队内成员自测;authed 路径, 创建 preview session(不入 Participation 正式库, 不 enqueue 分析), 返回 `{session_id, ws_url}` |

### Outline

| Method | Path | 说明 |
|---|---|---|
| GET | `/studies/:id/guide/` | 返回 is_current=true 的 guide |
| POST | `/studies/:id/generate_guide/` | 基于 research_goal 生成 v1 |
| POST | `/studies/:id/guide/` | 保存新版本(前端编辑后) |
| POST | `/studies/:id/review_outline/` (SSE) | 打开 review chat session;流式返回 `{reply_markdown, proposed_changes, awaiting_user_decision}` |
| POST | `/studies/:id/apply_outline_changes/` | body: `{proposed_changes: [...]}` → 创建新版本 |
| POST | `/studies/:id/finalize_outline/` | 锁定 guide, `study.status → ready`, 生成 public slug |

### Screener / Stimulus

| Method | Path | 说明 |
|---|---|---|
| GET/PUT | `/studies/:id/screener/` | 单一 screener |
| POST | `/studies/:id/screener/generate/` | 自然语言 → 结构化草稿 |
| GET/POST | `/studies/:id/stimuli/` | 列表/上传 |
| PATCH/DELETE | `/studies/:id/stimuli/:sid/` | 修改/删除 |

### 受访者公开端点(免登录,按 slug)

| Method | Path | 说明 |
|---|---|---|
| GET | `/i/:slug/` | 返回 consent + screener schema(不含敏感 study 细节) |
| POST | `/i/:slug/screener/submit/` | 提交 screener,返回 pass/fail |
| POST | `/i/:slug/start/` | body: `{mode: audio|video}`,创建 Session,返回 session_id + WS URL(不再接受 preview 参数, 自测走 authed 路径) |
| WS | `/ws/interview/:session_id/` | 双向:上行音频帧 / 下行 TTS 音频 + 字幕 SSE |
| POST | `/i/session/:id/upload/` | 受访者附件上传 |
| POST | `/i/session/:id/complete/` | 结束 session,enqueue `analyze_session` |

### 分析 / Custom Report / Knowledge

| Method | Path | 说明 |
|---|---|---|
| GET | `/studies/:id/insights/` | 列出该 study 所有 SessionInsight |
| GET | `/studies/:id/report/` | 当前 StudyReport |
| POST | `/studies/:id/generate_report/` | 触发生成(enqueue Celery) |
| POST | `/studies/:id/custom_reports/` | 提问 → 同步返回 answer / chart / citations |
| GET | `/studies/:id/custom_reports/` | 历史 |
| PATCH | `/custom_reports/:id/` | 钉到看板 / 保存为洞察 |
| GET | `/knowledge/` | Knowledge 页首屏(统计 + 最近问答 + 建议问题) |
| POST | `/knowledge/ask/` | 跨 study 提问 |

### 招募

| Method | Path | 说明 |
|---|---|---|
| GET | `/studies/:id/recruit/link/` | 返回公开链接(如 study.status == ready) |
| POST | `/studies/:id/recruit/broadcast/` | 调用 CowAgent adapter 群发 |
| GET | `/studies/:id/recruit/deliveries/` | 投递状态列表 |

## AI Agent Design

所有 LLM 调用经 `merism.llm_gateway.client.get_client`,通过设置 `base_url=https://api.deepseek.com/v1` 切到 DeepSeek。

### Outline Review Agent

**Service**: `OutlineReviewService` (products/studies/backend/outline_review.py)

**Input**: `{research_goal, current_guide_json, chat_history, user_message}`

**Prompt skeleton**:
```
<role>
你是一名资深定性研究顾问,审查访谈提纲。
</role>

<research_goal>
{research_goal}
</research_goal>

<current_guide>
{guide_json}
</current_guide>

<review_dimensions>
1. privacy: 是否含 PII 敏感问题
2. ordering: warmup → core → closing 节奏是否合理
3. structure: 是否覆盖 research_goal 各面向
4. bias: 引导性 / 双重否定 / 负载性措辞
5. followup_depth: 是否配置合理(敏感题不宜深)
6. alignment: 每题是否服务于 research_goal
</review_dimensions>

<rules>
- 禁止替用户决定:必须以"你希望……?"结尾
- 每条建议必须对应一个 proposed_change(op: modify_question | insert_question | remove_question)
- 给出 reply_markdown + proposed_changes + awaiting_user_decision
</rules>

<chat_history>
{history}
</chat_history>

User: {user_message}
```

**Function schema** (OpenAI tool):
```json
{
  "name": "review_outline",
  "parameters": {
    "type": "object",
    "properties": {
      "reply_markdown": {"type": "string"},
      "proposed_changes": {
        "type": "array",
        "items": {
          "oneOf": [
            {"properties": {"op": {"const": "modify_question"}, "question_id": {"type": "string"}, "new_text": {"type": "string"}, "reason": {"type": "string"}}},
            {"properties": {"op": {"const": "insert_question"}, "after_id": {"type": "string"}, "question": {"type": "object"}}},
            {"properties": {"op": {"const": "remove_question"}, "question_id": {"type": "string"}}}
          ]
        }
      },
      "awaiting_user_decision": {"type": "boolean"}
    }
  }
}
```

**Apply logic** (`apply_outline_changes`):
- 在事务中读取 is_current guide
- 按 proposed_changes 顺序 patch sections JSON
- 写新 guide row: `version += 1, is_current=True`,把旧版本 `is_current=False`

### Interview Moderator Agent

**Service**: `merism.conductor.moderator.stream_turn` (`merism/conductor/moderator.py`)

**Runtime model**: 每次 user turn 在同一个 `stream_turn` 协程内顺序执行两次 LLM call：(1) 非流式 `coverage_steer` 返回结构化 `ModeratorDecision`（function calling）；(2) 流式 `generate` 输出"下一句话"逐 token 推给 TTS。两节点之间穿插服务端硬规则校验 `decision_validator`（见 Req 14）。

**Conversation state**(内存中,结束时落到 InterviewSession.transcript):
```python
@dataclass
class ConvState:
    session_id: str
    current_question_id: str       # 当前正在问的 q_id
    asked_count_per_q: dict[str, int]  # 该题已追问几次
    section_cursor: int
    question_cursor: int
    research_goal: str
    guide: dict
    stimulus_active: Optional[str] # 当前展示的 stimulus_id
    last_vl_description: Optional[str]  # 视频模式,最近一帧 VL 描述
    mode: Literal["audio", "video"]

    def remaining_followups(self) -> int:
        q = find_question(self.guide, self.current_question_id)
        return max(0, q.followup_depth - self.asked_count_per_q.get(self.current_question_id, 0))
```

**Prompt skeleton**:
```
<role>
你是一名友善、耐心的访谈主持人。自然地说中文(或受访者选择的语言),简短、开放式提问。
</role>

<research_goal>{...}</research_goal>

<current_question>
text: {text}
probe_directions: {probes}
</current_question>

{% if stimulus_active %}
<current_stimulus>
kind: {kind}
description: {description}
</current_stimulus>
{% endif %}

<remaining_followups>{n}</remaining_followups>

{% if mode == "video" and last_vl_description %}
<vision_context>
{last_vl_description}
</vision_context>
{% endif %}

<rules>
1. 每轮只说一句话(1-3 句),不长篇说教
2. 若 remaining_followups > 0 且受访者回答浅,可追问(next_action=followup)
3. 若 remaining_followups == 0,必须 move_on
4. 若受访者明显不想回答,clarify 或 move_on,不硬逼
5. 若所有题问完,next_action=close
</rules>

<transcript>
{recent_turns}
</transcript>

请一边说下一句,一边在 tool call 决定 next_action。
```

**Function schema**:
```json
{
  "name": "next_turn",
  "parameters": {
    "type": "object",
    "required": ["spoken_text", "next_action"],
    "properties": {
      "spoken_text": {"type": "string"},
      "next_action": {"enum": ["followup", "move_on", "clarify", "close"]},
      "next_question_id": {"type": "string"}
    }
  }
}
```

**合规**:
- 单次 LLM call 同时流式生成 `spoken_text`(文本推 TTS 和字幕)+ 尾部 function call(决定 next_action)
- `remaining_followups == 0` → 强制在构造 prompt 时注明,并在解析后 double-check(防 LLM 不遵从)
- 每轮生成后,state 更新 `asked_count_per_q[current_question_id] += 1`(若 followup)或推进 cursor(若 move_on)

**WS 协议**(浏览器 ↔ Django):
```
client -> server:
  { "type": "audio_chunk", "data": "<base64 PCM>" }
  { "type": "upload_attachment", "url": "s3://..." }
  { "type": "end" }

server -> client:
  { "type": "stt_partial", "text": "..." }
  { "type": "stt_final", "text": "...", "ts_start": 12.5, "ts_end": 14.2 }
  { "type": "tts_chunk", "data": "<base64 OGG opus>" }
  { "type": "caption", "text": "...", "is_final": false }
  { "type": "stimulus_change", "stimulus_id": "s1" | null }
  { "type": "session_end" }
```

**视频模式抽帧**:
- 前端每 10 秒通过 HTTP `POST /i/session/:id/frame/` 上传 JPEG
- 后端同步(或 asyncio.create_task)调用 Qwen-VL-Max 生成描述,写 `vision_frames` 表并更新 ConvState
- 下一次 LLM call 注入最近 VL 描述

### Analysis Agent

**(A) 个体分析** — `analyze_session(session_id)` Celery task

```python
@shared_task(bind=True, max_retries=3)
def analyze_session(self, session_id: str) -> None:
    session = InterviewSession.objects.select_related("participation__study").get(pk=session_id)
    if session.participation.is_preview:
        return  # preview 不分析
    study = session.participation.study
    transcript = session.transcript
    guide = study.interviewguide_set.get(is_current=True)

    with scoped_capture(team_id=study.team_id) as capture:
        prompt = build_session_insight_prompt(study.research_goal, guide.sections, transcript)
        resp = llm_client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[{"role": "system", "content": prompt}],
            tools=[SESSION_INSIGHT_TOOL],
            tool_choice={"type": "function", "function": {"name": "emit_session_insight"}},
        )
        insight_data = parse_tool_call(resp)
        SessionInsight.objects.update_or_create(
            session=session,
            defaults={
                "team_id": study.team_id,
                "summary": insight_data["summary"],
                "highlights": insight_data["highlights"],
                "tags": insight_data["tags"],
                "extracted_tasks": insight_data["extracted_tasks"],
            },
        )
        capture("insight_generated", properties={"study_id": study.id, "session_id": session.id})
```

**Tag 维度自动推导**:
- prompt 中要求 LLM "从 research_goal 和 outline 推导 3-6 个分析维度,每个维度给出该 session 的取值"
- 例: research_goal 为满意度调研 → dimensions = `["sentiment", "specific_pain_points", "recommendation_likelihood"]`
- 跨 session 的维度一致性由 **StudyReport 生成阶段**做对齐(AI 合并相似维度)

**(B) 群体分析** — `generate_study_report(study_id)` Celery task

Step 1: 收集所有 SessionInsight,把 `tags` 维度做聚类(LLM 合并相似维度名,产出统一 schema)
Step 2: 按 Guide Question 聚合答案(quant_panel 柱状图数据)
Step 3: 按维度聚合(insight_nuggets)
Step 4: 为每个主要发现挑 2-3 条 quote(qual_panel)
Step 5: 汇总成 exec_summary
Step 6: 写 StudyReport row

**(C) Custom Report** — `CustomReportService.ask(study_id | None, user, question)`

```python
def ask(self, *, study_id: int | None, team_id: int, user, question: str) -> CustomReportQuery:
    # 1. Retrieve
    chunks = self._retrieve(team_id=team_id, study_id=study_id, query=question)
    # 2. LLM with function tools
    tools = [AGGREGATE_TAG, FILTER_SESSIONS, CITE_QUOTE]
    # tool 执行时,实际计算在 Python 端完成 (看 tool executor)
    resp = self._llm_with_tools(question, chunks, tools)
    answer, chart, citations = parse_custom_report_response(resp)
    return CustomReportQuery.objects.create(
        team_id=team_id,
        study_id=study_id,
        user=user,
        question=question,
        answer_markdown=answer,
        chart_spec=chart,
        citations=citations,
    )
```

**Retriever**:
- Phase 1(MVP): 简单基于 Postgres 全文检索 + study/research_goal 相似度过滤
- Phase 2(后续):切到 pgvector 做 semantic search(有独立 spec `s5-pgvector-embedding` 进行中)

**Tool executor** (`aggregate_tag`, `filter_sessions`, `cite_quote`):
- `aggregate_tag(tag_name)` → 查 SessionInsight.tags 下该维度的分布 → 返回 `{values: [...], counts: [...]}`
- `filter_sessions(criteria)` → 按 tag / screener 答案 filter → 返回 session_id 列表
- `cite_quote(session_id, ts_start, ts_end)` → 查 transcript 对应 span → 返回原文 + speaker

## Frontend Design

### 目录结构(新增)

```
products/studies/frontend/
├── create/
│   └── CreateStudyModal.tsx
├── study/
│   ├── StudyScene.tsx            # 外壳 + tabs 路由
│   ├── brief/
│   ├── outline/
│   │   ├── OutlineEditor.tsx
│   │   ├── QuestionCard.tsx
│   │   ├── OutlineReviewDrawer.tsx
│   │   └── outlineReviewLogic.ts  # kea
│   ├── screener/
│   ├── stimuli/
│   ├── recruit/
│   ├── analysis/
│   │   ├── AnalysisPage.tsx
│   │   ├── MainReport.tsx
│   │   └── CustomReportSidebar.tsx
│   └── knowledge/
├── interview/                    # 受访者房间
│   ├── InterviewRoom.tsx
│   ├── InterviewLeftPane.tsx     # AI + 摄像头 + 刺激物
│   ├── InterviewRightPane.tsx    # 字幕 + 附件 + 消息流
│   ├── interviewLogic.ts         # kea,管理 WS / state / 刺激物切换
│   └── consent/                  # consent + screener + 准备页
└── knowledge/
    └── KnowledgeExplorePage.tsx
```

所有组件从 `~/lib/merism` 导入 primitives:
```tsx
import { Button, Card, Select, Input, Textarea, Drawer } from '~/lib/merism/primitives'
import { colors, spacing, radii } from '~/lib/merism/tokens'
```

### 关键 Kea Logic

**outlineReviewLogic** (产物):
```ts
actions: {
  openReview: () => void
  sendMessage: (text: string) => void
  receiveStreamChunk: (chunk: { reply_markdown?: string; proposed_changes?: Change[] }) => void
  acceptChange: (changeIdx: number) => void
  acceptAll: () => void
  applyAll: () => void  // POST /apply_outline_changes
}
reducers:
  messages: []
  currentProposedChanges: []
  accepted: Set<number>
selectors:
  hasAcceptedAny
listeners:
  sendMessage → fetch SSE /review_outline → receiveStreamChunk
  applyAll → api call → updateGuide
```

**interviewLogic** (受访者端):
```ts
values:
  sessionId, mode, wsConnection, currentQuestionId, stimulusActive,
  captionText, sttPartial, transcript[]
actions:
  startSession, sendAudioChunk, receiveTTSChunk, receiveCaption,
  switchStimulus, uploadAttachment, endSession
listeners:
  startSession → open WS → subscribe
  receiveTTSChunk → play via MediaSource
  stimulusChange → update state (left pane 覆盖)
```

### 分析页布局细节

- 主区宽度占 `flex-1`,右侧 sidebar 固定 `w-[400px]`,双向独立滚动
- `MainReport`:按 Guide Question 循环渲染,每题一行 `grid-cols-12`,左 5 列定量图,右 7 列定性文本 + quotes
- `CustomReportSidebar`:`flex flex-col h-screen`,顶部输入框,中间 `overflow-y-auto`,底部快捷按钮
- Chart 组件:首选 ECharts(中文更友好),统一封装 `<MerismBarChart data={chart_spec} />`

### 受访者房间布局

```tsx
<div className="h-screen bg-gray-100 flex flex-col">
  <TopNav />
  <div className="flex-1 flex">
    <div className="w-2/3 p-8 flex flex-col items-center gap-6">
      <Tag size="sm" variant="muted">AI INTERVIEWER</Tag>
      <h2 className="text-2xl leading-relaxed text-center">{currentQuestion.text}</h2>
      <BeginResponseButton onClick={toggleRecording} />
      <PreviewFrame mode={mode} stimulus={stimulusActive} />
    </div>
    <aside className="w-1/3 border-l bg-white flex flex-col">
      <CaptionStream />
      <AttachmentUpload />
      <MessageFlow />
      <TextFallbackInput />
    </aside>
  </div>
</div>
```

## External Services Integration

### LLM: DeepSeek via merism.llm_gateway.client.get_client

```python
# products/studies/backend/llm.py
from merism.llm_gateway.client.get_client import OpenAI

def get_llm(model: str = "deepseek-chat") -> OpenAI:
    return OpenAI(
        api_key=settings.MERISM_LLM_API_KEY,
        base_url="https://api.deepseek.com/v1",
    )
    # Trace / cost recording happens in `merism.memai.llm.get_llm`
    # via Langfuse auto-instrumentation (no-op when keys absent).
```

- Outline Review / Custom Report 用 `deepseek-chat` (v3)
- Analysis (session insight, study report) 用 `deepseek-reasoner`
- Interview Moderator 用 `deepseek-chat` with streaming

### TTS: Qwen CosyVoice

```python
# products/studies/backend/tts.py
class CosyVoiceClient:
    async def stream_tts(self, text_stream: AsyncIterator[str]) -> AsyncIterator[bytes]:
        """text 流入 → OGG/Opus 音频字节流出"""
```

### STT: Qwen Paraformer

```python
# products/studies/backend/stt.py
class ParaformerClient:
    async def stream_stt(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[STTEvent]:
        """audio(PCM) → partial + final transcripts"""
```

### Vision: Qwen-VL-Max

```python
def describe_frame(jpeg_bytes: bytes, *, context: str) -> str:
    """视频抽帧 → VL 描述(80-120 字)"""
```

### Object Storage

复用 `merism.services.storage`:
- 录像 key(仅 video 模式): `merism/sessions/{session_id}/video.webm`
- 刺激物 key: `merism/stimuli/{study_id}/{filename}`
- 附件 key: `merism/attachments/{session_id}/{filename}`
- audio 模式不落盘任何音频文件(实时喂 STT 后即丢弃);video 模式只存一条视频轨(音频内嵌于 webm), 不单独存纯音频

### CowAgent Recruitment

复用 `products/studies/backend/recruitment/`(已在 Phase 0 完成),通过 `Recruitment_Broadcast` 接口调用 adapter。

## Settings

所有 `MERISM_*` settings 统一放在 `merism/settings/base.py` 的 annotated block 中:

```python
# --- MERISM ---
MERISM_DEEPSEEK_API_KEY = os.getenv("MERISM_DEEPSEEK_API_KEY", "")
MERISM_QWEN_API_KEY = os.getenv("MERISM_QWEN_API_KEY", "")
MERISM_QWEN_TTS_MODEL = os.getenv("MERISM_QWEN_TTS_MODEL", "cosyvoice-v1")
MERISM_QWEN_STT_MODEL = os.getenv("MERISM_QWEN_STT_MODEL", "paraformer-realtime-8k-v1")
MERISM_QWEN_VL_MODEL = os.getenv("MERISM_QWEN_VL_MODEL", "qwen-vl-max")
MERISM_REPORT_SESSION_THRESHOLD = int(os.getenv("MERISM_REPORT_SESSION_THRESHOLD", "10"))
MERISM_SESSION_COST_ALERT_CENTS = int(os.getenv("MERISM_SESSION_COST_ALERT_CENTS", "1000"))  # $10
MERISM_VIDEO_FRAME_INTERVAL_SEC = int(os.getenv("MERISM_VIDEO_FRAME_INTERVAL_SEC", "10"))
# --- /MERISM ---
```

Feature flags(env vars 同一 block):
- `MERISM_INTERVIEW_VIDEO_MODE` — 是否允许视频模式
- `MERISM_KNOWLEDGE_EXPLORE` — 跨 study 知识库开关
- `MERISM_IM_RECRUITMENT` — (已有)

## Security

- Study slug(`/i/:slug`)用 32 字节 URL-safe token,不可枚举
- Preview 模式仅通过 `/api/projects/:team_id/studies/:id/preview_session/` 启动,依赖 Django session auth + team membership 校验;不生成任何带 token 的外部链接,不在受访者公开路径 `/i/:slug` 上挂 preview 参数
- 受访者端点不暴露 `team_id`, `study_id`, `owner_id`;只返回 slug 内部可见的内容
- 附件上传:限制大小(图 10MB / 视频 100MB / PDF 20MB),MIME 白名单校验
- Channel_Config secret fields Fernet 加密(复用 `products/studies/backend/recruitment/` 已有方案)
- 所有 DRF viewset 通过 `self.context["get_team"]()` 获取 team,禁止从请求 body 读 `team_id`

## Error Handling

| 场景 | 行为 |
|---|---|
| LLM 调用超时 | 重试 2 次,指数退避;最终失败则 session 标记 `error`,不丢已有 transcript |
| LLM 返回非法 function call | 解析失败时降级:Outline Review 回退纯文本回复(无 proposed_changes);Moderator 强制 `next_action=move_on` |
| WS 断线 | 前端 reconnect,后端 ConvState 持久化在 Redis(TTL 30 min),断线续传 |
| STT 失败 | 提示用户切文字输入,继续流程 |
| TTS 失败 | 降级为纯字幕模式,显示提示"语音合成失败,请看字幕" |
| 受访者 session 中断超过 10 min | 后台 Celery `reap_stale_sessions` 标为 `dropped`,enqueue `analyze_session`(如 transcript 长度足够) |
| Analysis 失败 | Celery 重试 3 次,失败告警到 study owner |

## Testing Strategy

分两个 pytest 入口:

**轻量单测** (`pytest -c products/studies/pytest.ini`):
- 纯业务逻辑:prompt 构造、proposed_changes apply、ConvState 状态转移、chart_spec 验证
- 不依赖 DB
- Mock `merism.llm_gateway.client.get_client` 的响应;snapshot 测试 prompt 构造

**ORM 测试** (`pytest -c products/studies/pytest.orm.ini`):
- Model / serializer / viewset 集成
- Celery task 端到端(with eager mode)
- API 按 team 隔离的权限测试

**E2E (Playwright)** (`hogli test` 自动检测):
- 创建 study → 生成提纲 → 自测访谈(mock LLM) → 看 insight
- 受访者端:consent → screener → 准备页 → 房间 → 完成
- 分析页 Custom Report 问答闭环

**参数化**:
- `parameterized.expand` 覆盖 followup_depth ∈ {0, 1, 2, 3} 的行为
- 覆盖 mode ∈ {audio, video} 的分支
- 覆盖 proposed_changes 各 op 组合

**固定 fixture**:
- `fake_llm_response(content, tool_calls=[...])`
- `study_with_guide(research_goal, n_questions)`
- `completed_session(study, mode)`

## Migration Plan

1. 新 migration 加列:`InterviewSession.mode`, `InterviewSession.vision_frames`, `InterviewSession.cost_cents`, `Participation.is_preview`
2. 新 migration 建表:`merism_screener`, `merism_stimulus`, `merism_study_report`(如未建), `merism_custom_report_query`
3. Data migration: 不动已有 StudyGoal / StudyTransition / conductor policies 表(保留向后兼容)
4. 对已有 Study row:`research_goal` 若为空,从第一个 StudyGoal 取文本填入

## Cost Model (参考,不构成 SLA)

| 单场访谈(15 min) | 音频 | 视频 |
|---|---|---|
| STT(Paraformer) | ~$0.3 | ~$0.3 |
| LLM(DeepSeek, 含 moderator + insight) | ~$1.0 | ~$1.0 |
| TTS(CosyVoice) | ~$0.8 | ~$0.8 |
| Vision(Qwen-VL, 每 10s 一帧 × 90 帧) | - | ~$3-5 |
| 存储(S3) | 0(不存音频) | ~$0.05 |
| **合计** | **~$2-3** | **~$5-8** |

告警阈值默认 $10/场。

## Non-Goals(见 Requirement 26)

重复列举,防止 scope 扩张:
- 不实现独立的 conductor 3 层架构
- 不实现 coverage / engagement / off_topic policies
- 不做分析维度的独立 UI
- audio 模式不保留音频文件, 只留 transcript
- Preview 不做外部链接 + token 方案, 只走 authed 按钮
```

---

