# Dual-Layer Followup Design

## 背景

现状分析（借鉴 Typebot 的设计理念重审）:

Typebot 的设计哲学: **追问是研究者设计时的明确意图, runtime 确定性执行**。
- Condition System (命中条件) → Edge (指向追问 block) → runtime 强制执行
- AI 只生成内容，不决定"要不要追问"

Merism 现状:
- 每道题有 `probe_policy` (none/light/deep) + `max_probes` + `probe_directions`
- `coverage_steer` LLM 单点决策 "追问 or 跳过"
- `decision_validator` 有 3 条服务端规则强制约束
- **问题**: 只能追问研究者预设的方向; 受访者提到研究者没预想到的价值点时, AI 要么硬生生跳过(浪费), 要么过度追问(跑偏)

## 目标

建立两层追问机制:

```
Layer 1 — 预设追问 (Preset Probe)
  研究者在提纲里声明: "这道题必须追问 N 轮, 方向 X/Y"
  → runtime 强制执行, LLM 只管话术
  → 相当于 Typebot 的 condition → preset block

Layer 2 — 动态追问 (Dynamic Probe) 
  研究者在提纲里开关: "允许 AI 在检测到 X/Y/Z 信号时额外追问 M 轮"
  → 必须研究者显式开启 + 明确触发条件
  → LLM 可以触发, 但受 max_extra_rounds 硬上限约束
```

**核心原则**: 研究者完全控制"下限保证"和"上限探索"。AI 在研究者划定的框架内有灵活性，但不能越界。

## 数据模型变更

### Question schema (JSON field on InterviewGuide.sections)

**现状**:
```json
{
  "id": "q1",
  "text": "...",
  "intent": "...",
  "probe_policy": "light",
  "max_probes": 2,
  "probe_directions": ["具体例子", "对工作影响"],
  "required": true,
  "linked_stimulus_ids": []
}
```

**新增** (向后兼容, 缺字段时按现有行为):
```json
{
  ...既有字段...
  "dynamic_probe": {
    "enabled": false,
    "max_extra_rounds": 1,
    "triggers": ["new_theme", "contradiction", "strong_emotion", "surprise_finding"]
  }
}
```

### ExecutionState 变更

**新增字段**:
```python
# Per-question dynamic probe budget tracking.
# {question_id: {"asked": int, "budget": int}}
dynamic_probes_used: dict[str, dict[str, int]]
```

### ModeratorDecision 变更

**新增字段**:
```python
probe_kind: Literal["preset", "dynamic"] | None = None
# "preset"  — uses preset probe_directions, counts against max_probes
# "dynamic" — uses dynamic trigger, counts against max_extra_rounds

dynamic_trigger: Literal["new_theme", "contradiction", "strong_emotion", "surprise_finding"] | None = None
# Required when probe_kind == "dynamic"; must be in question's allowed triggers.
```

## Validator 新规则

延续现有 Rule 1-2, 新增:

**Rule 3 — Dynamic probe requires opt-in**:
  `probe_kind=="dynamic"` AND `dynamic_probe.enabled==false` → force `preset`
  If preset budget exhausted → force `move_on`.

**Rule 4 — Dynamic trigger must be in allowed list**:
  `probe_kind=="dynamic"` AND `dynamic_trigger` not in `question.dynamic_probe.triggers` → force `preset`
  If preset budget exhausted → force `move_on`.

**Rule 5 — Dynamic probe budget cap**:
  `probe_kind=="dynamic"` AND `dynamic_probes_done >= max_extra_rounds` → force `move_on`.

**Rule 6 — Preset exhausted but dynamic available**:
  `probe_kind=="preset"` AND preset exhausted AND dynamic still has budget AND triggered signal → allow upgrade to dynamic.

## Prompt 变更

`decision_prompt.py` 的 `<current_question_state>` 块新增:

```
dynamic_probe_enabled: true/false
dynamic_probe_remaining: N
dynamic_probe_triggers: ["new_theme", "contradiction", ...]
dynamic_probes_done:   M
```

LLM 指令新增:
> 如果检测到受访者提到了与当前问题相关但研究者未预设的**意外洞察**,
> 且 `dynamic_probe.enabled == true`, 且信号匹配 `dynamic_probe.triggers`,
> 且 `dynamic_probes_done < max_extra_rounds`, 你可以返回:
>   { "next_action": "followup", "probe_kind": "dynamic",
>     "dynamic_trigger": "<matched trigger>", "probe_triggered_by": "..." }
> 否则 probe_kind 必须是 "preset" (沿用 probe_directions)。

## 实施清单

1. `merism/conductor/state.py` — 加 `dynamic_probes_used` 字段 + helpers
2. `merism/conductor/prompts.py` — `ModeratorDecision` 加 `probe_kind` + `dynamic_trigger`
3. `merism/conductor/guide_cursor.py` — 加 `dynamic_probe_budget()` helper
4. `merism/conductor/decision_prompt.py` — 注入 dynamic_probe 配置
5. `merism/conductor/decision_validator.py` — 加 Rule 3/4/5/6
6. `merism/conductor/moderator.py` — `_apply_decision_to_state` 区分两种 probe
7. `merism/memai/agents/outline_review.py` — review 维度加"动态追问配置合理性"
8. 测试:
   - `test_decision_validator.py` — 新规则
   - `test_dynamic_probe.py` — 新增集成测试

## 不改动的部分

- AGENTS.md Rule 4: 仍是每 turn 两次 LLM call (decision + generation), 架构不变
- 前端提纲编辑器: 本 issue 只改后端 schema, 前端 UI 之后再接
- 现有问题保持兼容: 缺 `dynamic_probe` 字段 = `enabled: false`, 完全按现有行为
