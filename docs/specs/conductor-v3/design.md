# Conductor v3 — Design

> Implements `requirements.md`. Pattern reference: Google's `gemini-fullstack-langgraph-quickstart` (file split, state composition, `Configuration` loading, `Annotated[list, operator.add]` reducers, structured-output Pydantic).

---

## 0. Pattern provenance — what we borrowed from Google's reference

Five patterns lifted from `google-gemini/gemini-fullstack-langgraph-quickstart` (after reading `graph.py` + `state.py` + `configuration.py` + `tools_and_schemas.py` + `prompts.py`). Two patterns from that repo we deliberately **don't** apply, plus one we add that the reference doesn't need.

### Borrowed (apply throughout v3)

| # | Pattern | Where we apply it |
|---|---|---|
| 1 | **File split**: schema, state, tools_and_schemas, prompts, configuration, llm, nodes, graph each in their own module | `merism/conductor_v3/` layout (§1) |
| 2 | **State decomposition**: one `OverallState` TypedDict + per-node output TypedDicts (`JudgeOutput`, `AdvanceOutput`) | `state.py` (§3) |
| 3 | **`Annotated[list, operator.add]` reducer**: nodes return `[new_turn]`, LangGraph appends. No node ever returns the full list. | `OverallState.transcript` (§3) |
| 4 | **`Configuration` BaseModel + `from_runnable_config()` classmethod**: env > configurable > default precedence; LLM model / temperature swappable per call without restart | `configuration.py` (§6); every node calls `cfg = Configuration.from_runnable_config(config)` first |
| 5 | **Node signature `(state, config: RunnableConfig)`** with LLM constructed inside the node | `nodes.py` (§8) — every node is `def name(state, config: RunnableConfig) -> SomeOutputDict` |

### Borrowed-but-tweaked

| # | Google pattern | Our adaptation |
|---|---|---|
| 6 | **All prompts as module-level f-string templates** in one file, `.format(...)` at call site | `prompts.py` (§5) — 2 templates: `JUDGE_STANDARD_PROMPT / JUDGE_DEEP_PROMPT`. Each ends with the literal `返回 JSON:` line so DeepSeek's json_mode safety check passes (Google uses Gemini, no such constraint). |
| 7 | **Pydantic for structured LLM output** (`SearchQueryList`, `Reflection`) | `tools_and_schemas.py` (§4) — `Evaluation` Pydantic; constructed via `llm.with_structured_output(schema, method="json_mode")` (Google uses default `json_schema` method, which DeepSeek rejects — see Phase 0 spike). |

### Rejected (Google does, we don't)

| # | Google pattern | Why we skip it |
|---|---|---|
| 8 | **`Send("node", payload)` for parallel fan-out** (Google sends 3 web-research queries in parallel) | Interview is strictly sequential — one question at a time. Our `add_conditional_edges` returns plain literal targets. |
| 9 | **`builder.compile(name=...)` without checkpointer**; LangGraph Cloud injects Postgres saver at runtime | We self-host on Django, so checkpointer is wired at compile time: `builder.compile(checkpointer=PostgresSaver.from_conn_string(LG_CHECKPOINT_DB_URL))`. The checkpoint tables live in a dedicated namespace (`merism_lg_checkpoint*`) so they don't collide with `merism_*` Django tables. |

### Added (Google doesn't need it, we do)

| # | Pattern | Where |
|---|---|---|
| 10 | **`interrupt(payload)` + `Command(resume=text)` for human-in-the-loop** | `ask_and_wait` node (§8.2). Google's agent runs straight through to a final report; ours pauses at every question and waits for the participant's reply. |

### Code-level invariants enforced by these patterns

- **No LLM constructed at module top.** Every LLM lives inside the node that uses it. (Pattern 4 + 5.)
- **Every node returns a partial dict, never the full state.** State merge is done by LangGraph reducers + dict update. (Pattern 2 + 3.)
- **Every routing function is a pure function on state**, returning a literal node name or list of node names. **No LLM call inside a routing function** — that would violate AGENTS.md Rule 12. (Pattern 5.)
- **No `# noqa` to silence type errors on node signatures.** If pyright flags `JudgeOutput` vs `OverallState` mismatch, fix the type, not the suppression. (Pattern 2.)

These rules are reviewed in code review; PRs that violate them are rejected. ADR 0012 references this section as the binding architectural contract.

---

## 1. File layout

```
merism/conductor_v3/
├── __init__.py                    # public exports: graph, start_interview, answer_interview
├── schema.py                      # Outline / Section / Question / Turn (Pydantic, persistence shape)
├── state.py                       # OverallState / JudgeOutput / AdvanceOutput (TypedDicts, runtime shape)
├── tools_and_schemas.py           # Evaluation Pydantic (LLM structured-output contract)
├── prompts.py                     # all prompt templates as module-level strings
├── configuration.py               # Configuration BaseModel + from_runnable_config()
├── llm.py                         # build_llm() factory; DeepSeek json_mode adapter
├── nodes.py                       # ask_and_wait, judge_off, judge_standard, judge_deep, advance_cursor (5 nodes)
├── graph.py                       # StateGraph wiring + compile + checkpointer
├── runner.py                      # start_interview, answer_interview, get_interrupt_payload
├── persistence.py                 # finalize_to_session(): write transcript to InterviewSession.transcript
├── router.py                      # is_v3_session(session)
└── tests/
    ├── __init__.py
    ├── fakes.py                   # FakeLLM, RecordingChannel
    ├── fixtures/
    │   ├── __init__.py
    │   └── sample_outlines.py     # OUTLINE_3Q_BASIC, OUTLINE_5Q_LIVE, etc.
    ├── test_schema.py
    ├── test_state.py
    ├── test_configuration.py
    ├── test_prompts.py
    ├── test_nodes_prepare.py
    ├── test_nodes_ask.py
    ├── test_nodes_judge_off.py
    ├── test_nodes_judge_standard.py
    ├── test_nodes_judge_deep.py
    ├── test_nodes_advance.py
    ├── test_nodes_finish.py
    ├── test_graph_off_mode.py     # full traversal with mode=off
    ├── test_graph_standard_mode.py
    ├── test_graph_deep_mode.py
    ├── test_graph_resume.py        # interrupt → resume → checkpoint integrity
    ├── test_persistence.py         # finalize_to_session writes correct shape
    ├── test_router.py
    └── test_live_smoke.py          # @pytest.mark.merism_llm_live
```

Plus voice integration:
```
merism/voice/processors/moderator_v3.py
merism/voice/tests/test_moderator_v3_processor.py
```

---

## 2. Schema (`schema.py`)

Pydantic v2, `extra="forbid"` per AGENTS.md Pydantic conventions.

```python
QuestionFollowUpMode = Literal["off", "standard", "deep"]

class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, pattern=r"^[a-zA-Z0-9_]+$")
    ask: str = Field(min_length=1)
    follow_up_mode: QuestionFollowUpMode = "standard"
    probe_instruction: str | None = None
```

Researchers write 3 fields per question (`ask` + `follow_up_mode` +
optional `probe_instruction`); `id` is auto-generated by the frontend.
Per-mode follow-up budgets live in `Configuration` (not on the question).

```python
class Section(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, pattern=r"^[a-zA-Z0-9_]+$")
    title: str
    questions: list[Question]

class Outline(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal["v3"] = "v3"
    sections: list[Section]

class Turn(TypedDict):
    section_id: str
    question_id: str
    kind: Literal["main", "followup"]
    question: str
    answer: str
```

Validation helpers:
```python
def validate_outline(outline: Outline) -> None:
    """Raises OutlineError on duplicate ids, missing fields, etc."""

def flatten_questions(outline: Outline) -> list[tuple[Section, Question]]:
    """Section-and-question pairs in traversal order."""
```

---

## 3. State (`state.py`)

State decomposition follows Google's pattern: split TypedDicts by node-output concern; keep `OverallState` as the union.

```python
import operator
from typing import Annotated, Literal, TypedDict

class OverallState(TypedDict, total=False):
    # input — set by runner
    outline: dict                     # Outline.model_dump(); Pydantic doesn't go through TypedDict cleanly
    follow_up_mode: Literal["off", "standard", "deep"]

    # cursor — managed by ask_and_wait + advance_cursor
    section_i: int
    question_i: int
    probe_count: int

    # session-start expansion — managed by prepare_session
    probe_strategies: dict[str, str]   # qid -> expanded probe text

    # per-turn — managed by ask_and_wait + judge_*
    pending_probe: str | None
    last_answer: str
    last_evaluation: dict | None

    # accumulator — Annotated[list, operator.add] so each node returns only the new turn
    transcript: Annotated[list[Turn], operator.add]

    # terminal
    done: bool
    final_report: str | None
    last_error: str | None

class JudgeOutput(TypedDict, total=False):
    pending_probe: str | None
    probe_count: int
    last_evaluation: dict
    last_error: str | None

class AdvanceOutput(TypedDict, total=False):
    section_i: int
    question_i: int
    pending_probe: None
    probe_count: int
    done: bool
```

Reducer choice: `operator.add` for `transcript` is critical. Without it, each node return overwrites the list. The node returns `{"transcript": [new_turn]}`; LangGraph appends.

---

## 4. Tools and schemas (`tools_and_schemas.py`)

Single Pydantic model — the structured contract between LLM and engine.

```python
class Evaluation(BaseModel):
    sufficient: bool = Field(description="回答是否已经满足当前问题的目标")
    missing: list[str] = Field(default_factory=list, description="还缺哪些关键信息")
    followup: str | None = Field(default=None, description="如果需要追问, 只给一个自然、简短的问题")
    reason: str = Field(default="", description="判断理由, 供调试使用")
```

Same model for both `judge_standard` and `judge_deep` — only the prompt differs.

For `prepare_session`:
```python
class ProbeStrategies(BaseModel):
    strategies: dict[str, str] = Field(
        description="qid -> 扩展后的追问策略文本",
    )
```

---

## 5. Prompts (`prompts.py`)

Module-level f-string templates, all in one file. Format with `.format(...)`.

```python
PROBE_EXPAND_PROMPT = """你是访谈专家。
研究员给每道题写了简短的 probe instruction（追问方向）。
请把每条 probe instruction 扩展成 3-5 条具体的追问策略。
不要改写 ask / goal / must_get；只扩展 probe_instruction。

返回 JSON: {{"strategies": {{<qid>: <expanded_text>, ...}}}}

输入题目（含 probe_instruction）:
{questions_json}
"""

JUDGE_STANDARD_PROMPT = """你是访谈流程控制器, 不是闲聊助手。

判断标准（宽松）: must_get 中"大多数"要点已被回答提及即视为 sufficient=True。
不需要每点精确, 只要主要意思到位即可。

当前问题: {ask}
本题目标: {goal}
必须涵盖: {must_get}
追问策略（来自 probe_strategies, 用作生成追问的素材）:
{probe_strategy}

最近上下文:
{transcript_tail}

用户刚才回答:
{answer}

请判断:
1. sufficient 是否为 true
2. 不足时, 缺什么 (missing)
3. 不足时, 给一个自然、简短的追问 (followup)
4. 用户明显答不出 / 拒答, 直接 sufficient=true

返回 JSON: {{sufficient, missing, followup, reason}}
"""

JUDGE_DEEP_PROMPT = """你是严格的访谈流程控制器。

判断标准（严格）: must_get 中每一点都必须在回答中具体提及才算 sufficient=True。
模糊提及不算; 用户必须给出具体例子、频率、影响等可量化细节。

当前问题: {ask}
本题目标: {goal}
必须涵盖: {must_get}
追问策略（来自 probe_strategies, 用作生成追问的素材）:
{probe_strategy}

最近上下文:
{transcript_tail}

用户刚才回答:
{answer}

请判断:
1. sufficient 是否为 true（每点都需具体提及才 true）
2. 不足时, 缺什么 (missing)
3. 不足时, 针对最薄弱的维度生成 1 条精确追问
4. 用户明显答不出 / 拒答, 直接 sufficient=true

返回 JSON: {{sufficient, missing, followup, reason}}
"""

FINALIZE_PROMPT = """请基于下面的访谈记录, 生成结构化访谈总结 JSON。
要求:
1. 按主题归纳, 不要逐字复述
2. 提炼关键事实、痛点、动机、约束、机会点
3. 标出仍不明确的问题
4. 输出中文

返回 JSON: {{"summary": <markdown text>}}

访谈记录:
{transcript}
"""
```

All four templates use json_mode. DeepSeek requires the literal word "JSON" in the prompt — guaranteed by the `返回 JSON:` line in each template.

---

## 6. Configuration (`configuration.py`)

```python
class Configuration(BaseModel):
    judge_model: str = Field(default="deepseek-chat")
    finalize_model: str = Field(default="deepseek-chat")
    expand_model: str = Field(default="deepseek-chat")
    judge_temperature: float = Field(default=0.0)
    finalize_temperature: float = Field(default=0.3)
    deep_followups_multiplier: int = Field(default=2, ge=1, le=4)

    @classmethod
    def from_runnable_config(cls, config: RunnableConfig | None) -> "Configuration":
        configurable = config["configurable"] if config and "configurable" in config else {}
        raw = {n: os.environ.get(n.upper(), configurable.get(n)) for n in cls.model_fields}
        return cls(**{k: v for k, v in raw.items() if v is not None})
```

Per-team overrides arrive via `RunnableConfig.configurable` (e.g. `{"judge_model": "deepseek-reasoner"}`); env vars provide global defaults.

---

## 7. LLM factory (`llm.py`)

```python
def build_llm(model: str, *, temperature: float = 0.0) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        api_key=os.environ["MERISM_LLM_API_KEY"],
        base_url=os.environ["MERISM_LLM_BASE_URL"],
        temperature=temperature,
    )

def build_evaluator(llm: ChatOpenAI, schema: type[BaseModel]) -> Runnable:
    """DeepSeek requires method='json_mode' (default 'json_schema' is unsupported).
    Caller must ensure prompt contains 'JSON' (DeepSeek safety check)."""
    return llm.with_structured_output(schema, method="json_mode")
```

Spike result locked: `method="json_mode"` + prompt-contains-"JSON" gives 50/50 well-formed responses. `function_calling` only got 42/50; `json_schema` (default) got 0/50.

---

## 8. Nodes (`nodes.py`)

### 8.1 `prepare_session`

```python
def prepare_session(state: OverallState, config: RunnableConfig) -> dict:
    """Runs once at session start. Expands probe_instruction per question.
    Idempotent via checkpointer: re-invoking on resume is a no-op (checkpoint
    already past this node)."""
    cfg = Configuration.from_runnable_config(config)
    outline = Outline.model_validate(state["outline"])

    # Skip LLM call when no probe_instruction set
    questions_with_probe = [
        (s.id, q.id, q.probe_instruction)
        for s, q in flatten_questions(outline)
        if q.probe_instruction
    ]
    if not questions_with_probe:
        return {"probe_strategies": {}}

    try:
        llm = build_llm(cfg.expand_model, temperature=0.3)
        evaluator = build_evaluator(llm, ProbeStrategies)
        prompt = PROBE_EXPAND_PROMPT.format(questions_json=json.dumps(questions_with_probe, ensure_ascii=False))
        result: ProbeStrategies = evaluator.invoke(prompt)
        return {"probe_strategies": result.strategies}
    except Exception:
        logger.exception("conductor_v3.prepare_session.failed")
        return {"probe_strategies": {}}
```

### 8.2 `ask_and_wait`

```python
def ask_and_wait(state: OverallState, config: RunnableConfig) -> dict:
    section, qspec = current_section_and_question(state)
    pending = state.get("pending_probe")
    question_text = pending or qspec.ask
    kind: Literal["main", "followup"] = "followup" if pending else "main"

    answer = interrupt({
        "type": "question",
        "section_id": section.id,
        "question_id": qspec.id,
        "kind": kind,
        "question": question_text,
    })

    new_turn: Turn = {
        "section_id": section.id,
        "question_id": qspec.id,
        "kind": kind,
        "question": question_text,
        "answer": str(answer),
    }
    return {
        "last_answer": str(answer),
        "transcript": [new_turn],   # appended via operator.add reducer
    }
```

### 8.3 `judge_off`

```python
def judge_off(state: OverallState, config: RunnableConfig) -> JudgeOutput:
    """No LLM call. Always sufficient=True."""
    return {
        "pending_probe": None,
        "last_evaluation": {"sufficient": True, "skipped": True},
    }
```

### 8.4 `judge_standard`

```python
def judge_standard(state: OverallState, config: RunnableConfig) -> JudgeOutput:
    return _judge_with_prompt(state, config, JUDGE_STANDARD_PROMPT, multiplier=1)
```

### 8.5 `judge_deep`

```python
def judge_deep(state: OverallState, config: RunnableConfig) -> JudgeOutput:
    cfg = Configuration.from_runnable_config(config)
    return _judge_with_prompt(state, config, JUDGE_DEEP_PROMPT, multiplier=cfg.deep_followups_multiplier)
```

### 8.6 `_judge_with_prompt` (shared helper)

```python
def _judge_with_prompt(
    state: OverallState,
    config: RunnableConfig,
    template: str,
    *,
    multiplier: int,
) -> JudgeOutput:
    cfg = Configuration.from_runnable_config(config)
    _, qspec = current_section_and_question(state)
    probe_count = state.get("probe_count", 0)
    effective_max = qspec.max_followups * multiplier

    try:
        llm = build_llm(cfg.judge_model, temperature=cfg.judge_temperature)
        evaluator = build_evaluator(llm, Evaluation)
        prompt = template.format(
            ask=qspec.ask,
            goal=qspec.goal,
            must_get=qspec.must_get,
            probe_strategy=state.get("probe_strategies", {}).get(qspec.id, ""),
            transcript_tail=_format_transcript_tail(state, n=6),
            answer=state.get("last_answer", ""),
        )
        ev: Evaluation = evaluator.invoke(prompt)
    except Exception:
        logger.exception("conductor_v3.judge.failed")
        # advance on failure (Req 25)
        return {
            "pending_probe": None,
            "last_evaluation": {"sufficient": True, "reason": "judge_unavailable"},
            "last_error": "judge_call_failed",
        }

    should_probe = (
        not ev.sufficient
        and bool(ev.followup)
        and probe_count < effective_max
    )
    if should_probe:
        return {
            "pending_probe": ev.followup,
            "probe_count": probe_count + 1,
            "last_evaluation": ev.model_dump(),
        }
    return {
        "pending_probe": None,
        "last_evaluation": ev.model_dump(),
    }
```

### 8.7 `advance_cursor`

```python
def advance_cursor(state: OverallState, config: RunnableConfig) -> AdvanceOutput:
    outline = Outline.model_validate(state["outline"])
    section_i = state.get("section_i", 0)
    question_i = state.get("question_i", 0)

    current_questions = outline.sections[section_i].questions
    if question_i + 1 < len(current_questions):
        return {
            "question_i": question_i + 1,
            "pending_probe": None,
            "probe_count": 0,
        }
    if section_i + 1 < len(outline.sections):
        return {
            "section_i": section_i + 1,
            "question_i": 0,
            "pending_probe": None,
            "probe_count": 0,
        }
    return {
        "done": True,
        "pending_probe": None,
        "probe_count": 0,
    }
```

### 8.8 `finish_interview`

```python
def finish_interview(state: OverallState, config: RunnableConfig) -> dict:
    cfg = Configuration.from_runnable_config(config)
    transcript_md = _format_transcript_full(state.get("transcript", []))
    try:
        llm = build_llm(cfg.finalize_model, temperature=cfg.finalize_temperature)
        result = llm.invoke(FINALIZE_PROMPT.format(transcript=transcript_md))
        return {"final_report": result.content}
    except Exception:
        logger.exception("conductor_v3.finalize.failed")
        return {
            "final_report": f"<finalize failed: see logs>\n\n{transcript_md}",
            "last_error": "finalize_call_failed",
        }
```

---

## 9. Graph wiring (`graph.py`)

```
                         START
                           ↓
                    prepare_session     ← 1 LLM call (session start, optional)
                           ↓
                          ask           ← interrupt() for user answer
                           ↓
            ┌──────────────┼──────────────┐
            │              │              │
        judge_off    judge_standard   judge_deep
        (0 calls)     (1 LLM call)    (1 LLM call)
            │              │              │
            └──────────────┼──────────────┘
                           ↓
              route_after_judge
                  ↙          ↘
                ask         advance
                              ↓
                  route_after_advance
                       ↙        ↘
                     ask       finish     ← 1 LLM call (session end)
                                  ↓
                                 END
```

Code:
```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver

builder = StateGraph(OverallState, config_schema=Configuration)

builder.add_node("prepare_session", prepare_session)
builder.add_node("ask", ask_and_wait)
builder.add_node("judge_off", judge_off)
builder.add_node("judge_standard", judge_standard)
builder.add_node("judge_deep", judge_deep)
builder.add_node("advance", advance_cursor)
builder.add_node("finish", finish_interview)

builder.add_edge(START, "prepare_session")
builder.add_edge("prepare_session", "ask")

builder.add_conditional_edges(
    "ask",
    route_after_ask,
    {
        "judge_off": "judge_off",
        "judge_standard": "judge_standard",
        "judge_deep": "judge_deep",
    },
)

# All three judges feed into the same routing decision
for jnode in ("judge_off", "judge_standard", "judge_deep"):
    builder.add_conditional_edges(
        jnode,
        route_after_judge,
        {"ask": "ask", "advance": "advance"},
    )

builder.add_conditional_edges(
    "advance",
    route_after_advance,
    {"ask": "ask", "finish": "finish"},
)

builder.add_edge("finish", END)

graph = builder.compile(
    checkpointer=PostgresSaver.from_conn_string(settings.LG_CHECKPOINT_DB_URL),
    name="conductor-v3",
)
```

Routing functions:
```python
def route_after_ask(state) -> Literal["judge_off", "judge_standard", "judge_deep"]:
    mode = state.get("follow_up_mode", "standard")
    return f"judge_{mode}"

def route_after_judge(state) -> Literal["ask", "advance"]:
    return "ask" if state.get("pending_probe") else "advance"

def route_after_advance(state) -> Literal["ask", "finish"]:
    return "finish" if state.get("done") else "ask"
```

All routing pure functions — no LLM call. **AGENTS.md Rule 12 preserved**: AI is content-only, transitions are rule-driven.

---

## 10. Runner (`runner.py`)

```python
def graph_config(thread_id: str, *, configurable: dict | None = None) -> dict:
    return {
        "configurable": {
            "thread_id": thread_id,
            **(configurable or {}),
        }
    }

def start_interview(
    *,
    outline: Outline,
    thread_id: str,
    follow_up_mode: Literal["off", "standard", "deep"] = "standard",
    configurable: dict | None = None,
) -> dict:
    initial: OverallState = {
        "outline": outline.model_dump(),
        "follow_up_mode": follow_up_mode,
        "section_i": 0,
        "question_i": 0,
        "probe_count": 0,
        "probe_strategies": {},
        "pending_probe": None,
        "transcript": [],
        "done": False,
    }
    return graph.invoke(initial, config=graph_config(thread_id, configurable=configurable))

def answer_interview(*, user_answer: str, thread_id: str, configurable: dict | None = None) -> dict:
    return graph.invoke(
        Command(resume=user_answer),
        config=graph_config(thread_id, configurable=configurable),
    )

def get_interrupt_payload(result: dict) -> dict | None:
    interrupts = result.get("__interrupt__")
    if not interrupts:
        return None
    first = interrupts[0]
    if hasattr(first, "value"):
        return first.value
    if isinstance(first, dict) and "value" in first:
        return first["value"]
    return first
```

---

## 11. Persistence bridge (`persistence.py`)

The graph runs against LangGraph's `PostgresSaver`. At session completion, we copy the final transcript to `InterviewSession.transcript` (existing JSONField) so existing analytics/report code keeps working.

```python
async def finalize_to_session(session_id: str) -> None:
    """Called once after `finish` node emits final_report. Idempotent.
    Copies graph state's transcript + final_report into InterviewSession."""
    from merism.models import InterviewSession
    state = await graph.aget_state(graph_config(session_id))
    if not state or not state.values.get("done"):
        return
    transcript = state.values.get("transcript", [])
    final_report = state.values.get("final_report")
    await sync_to_async(_write_session)(session_id, transcript, final_report)

def _write_session(session_id: str, transcript: list[dict], final_report: str | None) -> None:
    InterviewSession.objects.filter(id=session_id).update(
        transcript={"turns": transcript},
        moderator_state={"final_report": final_report},
        status="completed",
    )
```

---

## 12. Routing (`router.py`)

```python
def is_v3_session(session: "InterviewSession") -> bool:
    if session.guide is None:
        return False
    sections = session.guide.sections
    return isinstance(sections, dict) and sections.get("version") == "v3"
```

Wired into:
- `merism/api/interview_message_view.py`: route v3 sessions to a new `run_v3_text_session(session, message)` async generator (built on `answer_interview`).
- `merism/realtime/voice.py`: when `is_v3_session(session)`, build pipeline `[STT, ModeratorV3Processor, TTS, ConversationState]`; otherwise existing v1.

---

## 13. Voice integration (`merism/voice/processors/moderator_v3.py`)

A pipecat `FrameProcessor` that bridges frames ↔ graph:

```python
class ModeratorV3Processor(FrameProcessor):
    def __init__(self, *, session_id: str, follow_up_mode: str):
        super().__init__()
        self._session_id = session_id
        self._mode = follow_up_mode
        self._graph_started = False
        self._idle_task: asyncio.Task | None = None
        self._idle_seconds = 60.0

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        if isinstance(frame, StartFrame):
            await self._bootstrap()
        elif isinstance(frame, TranscriptionFrame):
            await self._cancel_idle()
            await self._submit_answer(frame.text)
        elif isinstance(frame, EndFrame | CancelFrame):
            await self._cancel_idle()
        await self.push_frame(frame, direction)

    async def _bootstrap(self) -> None:
        outline = await load_outline_for_session(self._session_id)
        result = await asyncio.to_thread(
            start_interview,
            outline=outline,
            thread_id=self._session_id,
            follow_up_mode=self._mode,
        )
        await self._handle_graph_result(result)

    async def _submit_answer(self, text: str) -> None:
        result = await asyncio.to_thread(
            answer_interview,
            user_answer=text,
            thread_id=self._session_id,
        )
        await self._handle_graph_result(result)

    async def _handle_graph_result(self, result: dict) -> None:
        payload = get_interrupt_payload(result)
        if payload is not None:
            await self._push_question(payload["question"])
            self._start_idle_timer()
            return
        # No interrupt → graph reached END
        if result.get("final_report"):
            await finalize_to_session(self._session_id)
            await self.push_frame(EndFrame(), FrameDirection.DOWNSTREAM)

    async def _push_question(self, text: str) -> None:
        await self.push_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
        await self.push_frame(LLMTextFrame(text), FrameDirection.DOWNSTREAM)
        await self.push_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

    def _start_idle_timer(self) -> None:
        self._idle_task = asyncio.create_task(self._idle_after(self._idle_seconds))

    async def _idle_after(self, seconds: float) -> None:
        try:
            await asyncio.sleep(seconds)
            await self._submit_answer("")  # empty resume; judge will treat as insufficient or skip
        except asyncio.CancelledError:
            pass

    async def _cancel_idle(self) -> None:
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._idle_task
```

---

## 14. Database changes

Two migrations:

1. **Add column** `merism_interview_session.follow_up_mode VARCHAR(16) NOT NULL DEFAULT 'standard'` (Req 6).
2. **Create LangGraph checkpoint tables** via `PostgresSaver.setup()` — the saver creates its own `merism_lg_checkpoint` etc. tables; we run `setup()` in a Django data migration so checkpoint tables exist before first session.

`SessionEvent.kind` enum is unchanged; v3 does not write per-turn events. Existing v1 kinds remain.

---

## 15. Trade-offs documented (read this before code review)

1. **Rule 9 relaxation**: per-turn `SessionEvent` is no longer the runtime authority for v3. LangGraph's checkpoint table is. Analytics consumes `InterviewSession.transcript` (written once at `finish_interview`) instead of replaying events. ADR 0012 documents this; if you need event-level granularity later, a sink that mirrors graph events to `SessionEvent` can be added.
2. **2-LLM-call rule (Rule 4) shape change**: v1 was extract→generate (both per-turn). v3 is judge (per-turn) + finalize (per-session) + prepare (per-session, optional). Per-turn stays at most 1 LLM call (the judge); a second optional LLM call is `finalize_interview` at session end. The "2 calls per turn" envelope is preserved or reduced. AGENTS.md Rule 4 will be reworded to match.
3. **No skip_if / no behavior_slots**: explicit out-of-scope per Req §10. If research design needs branching, write a new ADR; don't extend v3 inline.
4. **No question rewriting**: questions are verbatim. Only `probe_instruction` is expanded once at session start. ADR 0012 locks this in.
