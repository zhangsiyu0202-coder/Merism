# 执行引擎研究：Typebot + Rasa 对比分析

> 日期：2026-05-21
> 目的：为 Merism 访谈执行引擎升级提供参考架构

---

## 一、研究背景

当前 Merism 的访谈执行模型是"每轮调 LLM 自由决策"——coverage_steer 每次从 transcript + guide 重新判断下一步。灵活但不可控，缺乏显式状态模型。

目标：将执行模型从"线性列表"升级为"列表驱动的状态机"。

---

## 二、Typebot 架构分析

仓库：https://github.com/baptisteArno/typebot.io
技术栈：TypeScript, Next.js, Prisma, PostgreSQL

### 2.1 数据模型

Typebot = groups + blocks + edges + variables + events

- Group: 画布上的节点组，包含 blocks 序列
- Block: 四类（Bubble输出 / Input等回复 / Logic决策 / Integration外部调用）
- Edge: { from: {blockId, itemId?}, to: {groupId, blockId?} }
- Variable: { id, name, value } 全局共享

### 2.2 执行引擎

核心循环 walkFlowForward():
1. 沿 edge 找到下一个 group
2. 遍历 group 内 blocks
3. Bubble → 输出，继续
4. Input → 停下等回复
5. Logic → 执行条件/跳转，返回 outgoingEdgeId
6. Integration → 调 AI/API，结果存变量
7. 循环直到遇到 Input 或无 nextEdge

用户回复后: 验证 → 存变量 → 找 outgoing edge → 继续 walkFlowForward

### 2.3 条件分支

Condition Block 支持 14 种比较操作（Equal/Contains/Greater/Regex 等），基于变量值选择不同 outgoing edge。纯确定性，不涉及 AI。

### 2.4 AI 集成

- AI 是被动的 Integration Block，不驱动对话
- 通过 forge 插件系统（OpenAI/DeepSeek/Anthropic）
- AI 输出存到 Variable，后续 Condition 可基于变量分支
- 流式两阶段：engine 返回 stream 信号 → 客户端调独立 endpoint
- Tools 在 isolated-vm 沙箱执行，maxSteps=6

### 2.5 追问实现（手动循环）

没有原生追问。需手动画：

```
[问题] → [AI判断Block] → [Condition]
                           ├── 不充分 → [追问Group] → edge回到[AI判断]
                           └── 充分 → [下一题]
```

每题追问需要：1个AI Block + 1个Condition + 1个追问Group + 循环edge + 计数器变量。
10题 × 3种追问 = 30+ groups + 50+ edges，配置成本极高。

### 2.6 Session 状态

ChatSession.state 是一个 JSON 字段，包含完整 typebot 定义 + currentBlockId + 变量值。完全可序列化，断线恢复零成本。

### 2.7 结果与分析

- 每个 Input 回答存为 Answer
- Analytics 只有 Views/Starts/CompletionRate
- 无 AI 分析能力，需导出 CSV 到外部工具

---

## 三、Rasa 架构分析

仓库：https://github.com/rasahq/rasa
版本：3.6.21
技术栈：Python, TensorFlow, asyncio

### 3.1 执行模型：事件驱动状态机

```
用户消息 → NLU(意图+实体) → Tracker追加事件 → Policy投票选action → 执行action → 产生事件 → 循环直到action_listen
```

### 3.2 Policy Ensemble（多策略投票）

- RulePolicy（最高优先级）：确定性规则，if intent==X → action Y
- MemoizationPolicy：精确匹配训练故事中的路径
- TEDPolicy：Transformer 模型，从故事中学习泛化

优先级：Rule > Memoization > TED。确定性兜底，ML做泛化。

### 3.3 Domain 定义

```yaml
intents: [greet, inform, deny]
entities: [cuisine, number]
slots:
  cuisine: { type: text, mappings: [from_entity: cuisine] }
responses:
  utter_ask_cuisine: [{text: "What cuisine?"}]
forms:
  restaurant_form:
    required_slots: [cuisine, num_people, preferences]
```

### 3.4 Form/Loop 机制（核心借鉴点）

声明式多轮数据收集循环：

```python
class FormAction(LoopAction):
    def required_slots(domain) -> [slot_names]
    def _find_next_slot_to_request(tracker):
        return next(slot for slot in required if slot.value is None)
    async def do():
        validate_input()
        request_next_slot()  # 自动问下一个空slot
    async def is_done():
        return all slots filled or manually terminated
```

特性：
- 声明 required_slots 即可，不需手动画循环
- 自动找下一个未填 slot 来问
- 支持 unhappy path（用户中途打断）
- 支持 slot validation
- is_done = 所有 required_slots 有值

### 3.5 DialogueStateTracker（事件溯源）

```python
tracker.events = [UserUttered, ActionExecuted, SlotSet, BotUttered, ...]
tracker.slots = {name: Slot}
tracker.active_loop = "form_name" or None
```

状态完全由事件流决定，可随时重放重建。

### 3.6 Slot 判断逻辑

```python
def _should_request_slot(tracker, slot):
    return tracker.slots[slot].value is None  # 有值=填了，None=没填
```

纯规则，不涉及 AI。不能判断回答质量/深度。

### 3.7 局限

- Slot 填充是二元的（有/无），不能判断"回答是否充分"
- Responses 是预写模板，不能动态生成
- NLU 依赖训练数据，冷启动成本高
- 追问需手动写 stories 定义路径

---

## 四、三者对比

| 维度 | Typebot | Rasa | Merism (现在) |
|------|---------|------|--------------|
| 执行模型 | DAG 图遍历 | 事件驱动状态机+策略投票 | 每轮调LLM自由决策 |
| 流程定义 | 可视化画布(groups+edges) | YAML(stories+rules+domain) | JSON(sections+questions) |
| 决策方式 | 确定性（沿edge走） | 混合（规则+ML+记忆） | 纯LLM |
| 状态 | SessionState(currentBlock+变量) | Tracker(事件流) | moderator_state(JSON) |
| 循环/追问 | 手动画edge回环 | Form声明required_slots | LLM每轮判断 |
| 中断处理 | 无 | Stories定义unhappy path | 无 |
| 可预测性 | 高（确定性） | 中（规则确定，ML概率） | 低（LLM黑盒） |
| 动态生成 | 需额外AI Block | 不支持（模板回复） | 原生支持 |
| 分析能力 | 无（导出CSV） | 无 | 强（SessionInsight+StudyInsights） |

---

## 五、核心发现

### 5.1 Typebot 的本质

Typebot 不追问时就是顺序执行（group1 → group2 → group3）。追问只是在某个 group 上通过 edge 形成循环。本质是"顺序 + 局部循环"。

### 5.2 Rasa Form 的本质

Form 是声明式循环：声明要收集哪些 slot，引擎自动循环问直到全部填满。判断"是否填满"是纯规则（value is None）。

### 5.3 两者都缺的

- 不能判断回答质量/深度（只能判断有/无）
- 不能动态生成追问内容（Typebot需预写，Rasa用模板）
- 不适合半结构化访谈场景

### 5.4 Merism 的优势

- coverage_steer 能判断回答是否"充分"（不只是有/无）
- generate node 能动态生成追问话术
- 2-node moderator 架构（decide + generate）已经是正确方案

### 5.5 Merism 的不足

- 缺乏显式状态模型（LLM每轮从零判断）
- 没有 per-question 的追问策略配置
- 没有变量系统（AI提取的信息无法被后续逻辑引用）
- 没有条件跳转（不能根据回答跳过某些题）

---

## 六、设计决策：列表驱动的状态机

### 6.1 核心思路

不做完整 DAG，不做画布编辑器。保持线性 outline 列表，但执行时用状态机：

```
默认顺序：q1 → q2 → q3 → ... → 结束
追问循环：在任意 question 上原地循环 0~N 次
```

等价于 Typebot 的"顺序 + 局部循环"，但不需要手动画 edge。

### 6.2 执行伪代码

```python
for question in guide_snapshot.questions:
    ask(question.text)
    answer = wait_reply()
    probe_count = 0
    while should_probe(answer, question) and probe_count < question.probe_depth:
        followup = generate_probe(answer, question.probe_hints)
        ask(followup)
        answer = wait_reply()
        probe_count += 1
    # 切到下一题
```

### 6.3 与现有架构的关系

- should_probe() = 现有 coverage_steer 的 "followup" 决策
- generate_probe() = 现有 generate node
- probe_depth = 现有 max_probes 的 per-question 版本
- probe_hints = 注入 coverage_steer prompt 的额外上下文

### 6.4 新增的 per-question 配置

```json
{
  "id": "q1",
  "text": "你平时怎么选购咖啡？",
  "probe_depth": 2,
  "probe_hints": ["追问决策因素", "追问具体场景"],
  "skip_if": "受访者明确表示不喝咖啡"
}
```

- probe_depth: 替代全局 max_probes，per-question 可配，默认继承 study 级别
- probe_hints: 注入 coverage_steer prompt，告诉 LLM 追问方向
- skip_if: 注入 coverage_steer prompt，满足条件跳过此题

### 6.5 为什么不用完整 DAG

- 定性访谈 90% 是线性的，只有追问和跳过是非线性
- DAG 配置成本高（10题×3追问=50+edges），研究员不会画
- 追问内容是动态的（取决于用户说了什么），设计时不可能穷举所有路径
- 列表+状态机覆盖所有需求，且零额外配置成本

### 6.6 为什么不用 Rasa 的 Form

- Form 的 is_done 是二元判断（slot有值/无值），不能判断回答深度
- Form 的回复是模板，不能动态生成
- 但 Form 的"声明式循环"思路值得借鉴：声明 questions 列表，引擎自动循环

---

## 七、实现路径

### Phase 1: per-question 配置（最小改动）

1. outline JSON schema 加 probe_depth / probe_hints / skip_if 字段
2. coverage_steer prompt 模板读取这些字段
3. 前端 outline 编辑器加对应 UI
4. 不改执行引擎，只改 prompt 注入

### Phase 2: 显式状态模型

1. moderator_state 加 current_question_phase: asking | probing
2. moderator_state 加 probe_count_for_current_question
3. decision_validator 基于 probe_depth 做硬规则兜底
4. 不再依赖 LLM 记住"已经追问了几次"

### Phase 3: 变量系统（可选）

1. moderator_state 加 extracted_variables: {}
2. 每轮 AI 自动提取关键信息存入
3. skip_if 可以引用变量做条件判断
4. 为后续条件跳转打基础

---

## 八、参考文件

### Typebot 关键源码

- `packages/bot-engine/src/walkFlowForward.ts` — 核心执行循环
- `packages/bot-engine/src/continueBotFlow.ts` — 用户回复处理
- `packages/bot-engine/src/blocks/logic/condition/executeConditionBlock.ts` — 条件判断
- `packages/bot-engine/src/blocks/logic/jump/executeJumpBlock.ts` — 跳转
- `packages/ai/src/runChatCompletion.ts` — AI 调用
- `packages/chat-session/src/schemas.ts` — Session 状态定义
- `packages/conditions/src/constants.ts` — 比较操作符

### Rasa 关键源码

- `rasa/core/processor.py` — 消息处理主循环
- `rasa/core/actions/loops.py` — LoopAction 基类
- `rasa/core/actions/forms.py` — FormAction（声明式循环）
- `rasa/core/policies/rule_policy.py` — 确定性规则策略
- `rasa/core/policies/ensemble.py` — 多策略投票
- `rasa/shared/core/trackers.py` — DialogueStateTracker
- `rasa/shared/core/events.py` — 事件类型定义

### Merism 现有相关代码

- `merism/conductor/moderator.py` — 2-node moderator (coverage_steer + generate)
- `merism/models/interview.py` — InterviewSession + guide_snapshot
- `frontend/src/features/studies/tabs/outline/outlineEditorLogic.ts` — Outline 编辑器
