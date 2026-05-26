# ADR 0011 — Framework evaluation for Conductor v2: pipecat-flows & LangGraph

Date: 2026-05-23
Status: superseded by ADR 0012 (decided to migrate to LangGraph; ADR 0011's deferral overruled by dogfeed feedback within 4 hours)
Related: ADR 0007 (superseded), ADR 0008 (retired), ADR 0009 (superseded by ADR 0012)

## Why this ADR exists

Two days after ADR 0009 landed, the question came up: should Conductor v2 be rebuilt on top of an existing conversational-flow framework instead of carrying our hand-rolled list interpreter (`merism/conductor_v2/engine.py`, ~502 LOC)?

This ADR captures the evaluation so a future engineer (or future-us) does not have to re-derive it. **Conclusion up front: stay on the list interpreter for now. Revisit if specific trigger conditions hit (§ Triggers).** This document records the analysis, not a commitment.

## Candidates evaluated

| Candidate | Verdict | One-line |
|---|---|---|
| **pipecat-flows** | Live option, 3 weeks if mapped 1 question = 1 node | Domain-aligned, same family as our voice stack, BSD-2 |
| **LangGraph** | Live option, 2 weeks if used as engine substrate (path B) | Generic state machine, MIT, big ecosystem, time-travel debug |
| Botpress | Excluded | v12 self-hosted is end-of-life; current product is closed cloud |
| Vocode | Excluded | Voice-only; redundant with pipecat; low maintenance velocity (last big push 2024) |
| AutoGen / CrewAI | Excluded | Multi-agent orchestration, wrong shape for single-moderator interview |
| DSPy | Excluded | Prompt optimization, not a conversation runtime |
| LiveKit Agents | Excluded | Voice-only, redundant with pipecat |

## Status quo: what v2 already is (one-page recap)

Per ADR 0009 and `docs/specs/conductor-v2/`:

- **Schema** — `Outline` / `Section` / `QuestionNode` / `SlotSchema` / `SkipIfRule` (6 operators) / `SessionState`. ~452 LOC, all `extra="forbid"` Pydantic.
- **Engine** — `run_interview` async loop iterates over questions; per question: `ai.extract` → check required_slots filled → `ai.generate` (probe or move on). 2 LLM calls per turn, no LLM call ever decides flow. ~502 LOC.
- **Persistence** — `SessionEvent` rows are authoritative (Rule 9). `reconstruct_state(events, outline)` rebuilds `SessionState` deterministically. `DBEventSink` writes monotonic seq.
- **Routing** — Rule 13 dispatch: `is_v2_session(session)` checks `guide.sections.version == "v2"` and routes to v2; otherwise v1 `stream_turn`.
- **Sinks** — `VoiceOutputSink` for pipecat pipeline (with 60s `IdleTimer`), `SSEOutputSink` for HTTP text mode.
- **Tests** — 150 passing (143 conductor_v2 + 7 voice processor). Live LLM PoC against DeepSeek: 50/50 calls, p95 1791ms, 9/10 scenarios at 5/5.

The v2 surface is small and well-tested. Any framework migration must clear that bar.

## Hard constraints any framework must honor

These come from `AGENTS.md` and are non-negotiable:

1. **Rule 4 — 2 LLM calls per turn**: extract + generate. No third call. No "AI decides next node" call.
2. **Rule 9 — Event sourcing is authoritative**: `SessionEvent` is the truth, `moderator_state` is a cache. Any framework state must serialize through `SessionEvent`.
3. **Rule 12 — AI is content-only; flow is rule-driven**: LLM produces typed slots + prose. Engine evaluates `SkipIfRule` over typed variables. Edges are deterministic.
4. **Rule 13 — Dual-engine routing during grace period**: v1 sessions route to `merism.conductor.moderator.stream_turn`; v2 routes to the v2 engine. A framework migration must keep this routing surface.
5. **DeepSeek + Qwen only** (Rule 5): no swapping providers to fit a framework's expectations.
6. **No new LLM providers / queues / data stores without an ADR** (Rules 5, 6).
7. **PostgreSQL + Redis only** (Rule 6): no Kafka, no ClickHouse, no vendor-specific persistence.
8. **Researcher mental model is a list of questions**, not a graph. Any framework UI must compile to/from list shape if exposed.

## Option A: pipecat-flows with `1 question = 1 node`

### What it is

`pipecat-ai/pipecat-flows` is an add-on framework for `pipecat` (which we already use for voice). Stars: 593. License: BSD-2-Clause. Latest: v1.1.0 (May 2026). Same maintainers as pipecat itself.

A flow is a graph of nodes. Each node has:
- `task_messages` — focused system prompt for this node
- `functions` — tool functions the LLM can call (typically extraction tools)
- transition functions — decide which node to enter next, can be **rule-driven** (no LLM involvement) or LLM-driven (LLM picks via tool call)

The framework integrates as a pipecat pipeline processor. State lives in `FlowManager.state` (dict).

### Mapping our v2 onto pipecat-flows

```
Outline.sections[*].questions[*]   →   one node per question
QuestionNode.required_slots        →   tool functions (record_<slot>)
QuestionNode.skip_if               →   conditional transition function (PURE RULE)
QuestionNode.max_probes            →   counter in node-local state, transition decides
warmup / closing                   →   start node / end node
SessionState.answers               →   FlowManager.state["answers"]
SessionState.behavior_slots        →   FlowManager.state["behavior_slots"]
SessionEvent                       →   bridge: pipecat-flows event → SessionEvent.append()
```

Researcher-facing UI does **not** change: still a list editor in the OutlineTab. We compile `Outline → pipecat-flows config` at session start.

### What this buys

- **Per-node focused context** — each question gets its own `task_messages`, instead of one giant prompt managing all questions. LLM has less to track per call.
- **Tool-call extraction** — `record_<slot>` function call shape is industry-standard. Better cross-provider portability.
- **Domain alignment** — pipecat-flows is built for "structured conversations", which is exactly our domain (vs. LangGraph's generic state machine).
- **Same family as voice** — we already use pipecat. A flow add-on means one less foreign concept in the codebase.
- **Visual debugging** — pipecat-flows has flow visualization. Useful for postmortem of a bad session.
- **Future sub-flows** — dynamic flows (build node graph at runtime) gives a clean place to land "complex multi-step questions" later, without our own ad-hoc abstraction.

### What it costs

- **DeepSeek tool-call reliability is unverified**: pipecat-flows requires LLM function calling. Our v2 uses structured-output (JSON schema response). All pipecat-flows examples use OpenAI / Anthropic / Gemini / Bedrock. **Must be PoC-validated before commitment** (see § Spike).
- **Text-mode adapter**: pipecat-flows assumes a long-running pipecat pipeline. Our text mode is HTTP one-turn-per-request. A bridge spins up a mini pipeline per HTTP request, with text source/sink processors and `FlowManager` save/restore. ~3 days. Not a blocker, but a meaningful chunk.
- **Event-bridge to SessionEvent**: pipecat-flows has its own internal events. We need a sink/listener that translates flow events → `SessionEvent` rows so Rule 9 (event sourcing) holds. ~3 days.
- **Test rewrite**: 150 tests do not survive a framework swap. Engine tests become flow-config tests + integration tests. ~1 week.
- **Migration command rewrite**: `migrate_guide_to_v2.py` produces v2 list shapes. If pipecat-flows config is the runtime form, the command needs updating. ~3 days.
- **Researcher UI does not change**, but the `OutlineTab` save path changes: still PUTs Outline JSON, but server compiles to flow config and stores both shapes. ~2 days.
- **Dependency**: `pipecat-ai-flows` + transitive deps. Smaller than LangGraph's tree because pipecat is already vendored.

**Total work: ~3 weeks of one engineer.**

### Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| DeepSeek tool calling unstable on multi-tool nodes | medium | blocking | Spike (1 day) before committing |
| Researcher writes outline → compiler bug → runtime divergence | medium | high | Round-trip tests: every Outline compiles + decompiles bit-identical |
| FlowManager state ↔ SessionEvent drift | medium | high | Event-sourcing test: save FlowManager state from session, replay SessionEvents, assert byte-equal state |
| pipecat-flows API churn (v1.x is recent) | low | medium | Pin exact version; vendor-fork if needed |
| Voice 60s idle semantics break | medium | medium | Keep `IdleTimer` outside flow framework, inject as transition trigger |

### Sketch (what the code would look like)

```python
# merism/conductor_v2/compile_to_flows.py  (new)
from pipecat_flows import FlowConfig, NodeConfig, FlowManager

def compile_outline_to_flow(outline: Outline) -> FlowConfig:
    nodes: dict[str, NodeConfig] = {}
    for question in flatten_questions(outline):
        nodes[question.id] = NodeConfig(
            role_messages=[{"role": "system", "content": INTERVIEWER_PERSONA}],
            task_messages=[{"role": "system", "content": render_question_prompt(question)}],
            functions=[
                _record_slot_fn(slot)
                for slot in question.required_slots
            ] + [_record_behavior_fn(b) for b in BEHAVIOR_SLOTS],
            # transition is a pure rule function — no LLM involvement
            transition_callback=lambda args, fm: _route_after_question(question, fm),
        )
    return FlowConfig(nodes=nodes, initial_node="__warmup__")

def _route_after_question(q: QuestionNode, fm: FlowManager) -> str:
    """Pure rule. Looks at fm.state["answers"][q.id], evaluates skip_if, returns next node id."""
    answers = fm.state["answers"][q.id]
    if not _required_slots_filled(q, answers):
        if fm.state["probe_budget_left"][q.id] > 0:
            return q.id  # re-enter to probe
        # gave_up; fall through to skip evaluation
    if q.skip_if and matches_skip_if(q.skip_if, answers):
        return q.skip_if.jump_to
    return _next_question_id(fm.state["outline"], q)
```

The `_route_after_question` is the analog of our current `engine.execute_question`'s tail; it stays a pure function, evaluates the same `SkipIfRule` over the same typed slots. **Rule 12 holds.**

## Option B: LangGraph as engine substrate (path B from earlier discussion)

### What it is

`langchain-ai/langgraph`, MIT, very active. Generic typed state-graph framework. Nodes are arbitrary Python functions over a typed state. Edges can be static or conditional. Built-in `PostgresSaver` checkpointer, `interrupt()` for human-in-the-loop, subgraph composition.

### Mapping our v2 onto LangGraph

Two nesting levels:

**Outer graph** — iterates over questions:
```python
class InterviewState(TypedDict):
    outline: Outline
    current_qid: str | None
    answers: dict[str, dict]
    behavior_slots: BehaviorSlots
    probe_budget_left: dict[str, int]
    transcript: list[Turn]

outer = (
    StateGraph(InterviewState)
    .add_node("warmup", play_warmup)
    .add_node("ask_question", question_subgraph)   # subgraph
    .add_node("closing", play_closing)
    .add_edge(START, "warmup")
    .add_edge("warmup", "ask_question")
    .add_conditional_edges(
        "ask_question",
        route_next_question,           # pure rule, evaluates skip_if
        {"next": "ask_question", "done": "closing"},
    )
    .compile(checkpointer=PostgresSaver(pool))
)
```

**Inner graph** (one per question) — extract / probe / record:
```python
inner = (
    StateGraph(QuestionState)
    .add_node("speak", emit_text_to_sink)
    .add_node("wait_reply", lambda s: interrupt({"awaiting": "user_reply"}))
    .add_node("extract", run_ai_extract)            # AI call 1 (content)
    .add_node("check", check_required_filled)      # pure rule
    .add_node("probe", run_ai_generate_probe)      # AI call 2 (content)
    .add_node("record", append_answer_event)
    .add_edge(START, "speak")
    .add_edge("speak", "wait_reply")
    .add_edge("wait_reply", "extract")
    .add_edge("extract", "check")
    .add_conditional_edges(
        "check",
        lambda s: "record" if s["filled"] else ("probe" if s["budget_left"] else "record"),
    )
    .add_edge("probe", "speak")
    .add_edge("record", END)
    .compile()
)
```

Researcher UI: unchanged. Server compiles `Outline → CompiledStateGraph` per session.

### What this buys

- **PostgresSaver checkpointer** is battle-tested. Replaces our `event_log.py` write path and `reconstruct_state` read path with a community implementation.
- **`interrupt()` is a clean primitive** for "wait for user reply" (HTTP) or "wait for STT final" (voice). Replaces our `OutputSink.wait_input()`.
- **Subgraph composition** is a first-class concept. If a future "concept testing" question needs a 4-step interaction, it is just a subgraph plugged into the outer chain.
- **Time-travel debugging**: rewind to any checkpoint and replay. Genuinely useful for diagnosing a bad session.
- **`astream`** — token streaming with backpressure, drop-in for our sinks.
- **No pipeline coupling**: works equally well in voice (driven by pipecat frames) and text (driven by HTTP requests). Cleaner separation than pipecat-flows for our dual-mode case.

### What it costs

- **40+ transitive dependencies** (langchain-core, langchain-community, etc.). Larger blast radius for upstream churn.
- **Engine, event_log, persistence rewrite**: ~990 LOC of our code goes away (good), replaced by ~300 LOC compiler + ~200 LOC LangGraph integration + custom `PostgresSaver` schema (or migrate `SessionEvent` to LangGraph's checkpoint table — likely not desirable since SessionEvent serves analytics).
- **Bridge `PostgresSaver` ↔ `SessionEvent`**: LangGraph stores checkpoints in its own table format. We need either (a) a custom saver that writes to `SessionEvent`, or (b) accept dual-write (LangGraph's table for resume, `SessionEvent` for analytics) — both have cost.
- **DeepSeek streaming integration** in LangChain — works but less first-class than OpenAI / Anthropic. Tool calling reliability is the same risk as pipecat-flows since LangGraph commonly uses tool-call patterns; we can sidestep by sticking to structured output, which works in LangChain.
- **Voice integration**: LangGraph is LLM-pipeline-centric, pipecat is frame-pipeline-centric. Bridging them is non-trivial — a `ModeratorV2Processor` would translate pipecat frames to graph events and back. Estimate: ~1 week, not 3 days.
- **Test rewrite**: ~80 of our 150 tests survive (schema, persistence, router, sinks); engine tests are replaced by graph compile + execute tests.

**Total work: ~2 weeks of one engineer.** Less than pipecat-flows because we are not coupling to pipecat's pipeline lifecycle for text mode.

### Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LangChain dep tree churn breaks builds | medium | low (pin versions) | Pin exact versions; vendor critical paths |
| `PostgresSaver` schema clashes with our migrations | low | medium | Use a dedicated checkpoint table separate from `merism_session_event` |
| Voice frame ↔ graph state bridge complexity | medium | medium | Keep `IdleTimer` and barge-in logic in pipecat-side processor; graph only sees "user finished a turn" events |
| `interrupt()` semantics differ between in-process and persistence-backed | medium | medium | Use persistence-backed interrupts only; never rely on in-process resume |
| Subgraph state isolation surprises | low | medium | Cover with subgraph round-trip tests |

## Side-by-side comparison

| Dimension | pipecat-flows (1q=1n) | LangGraph (path B) | v2 status quo |
|---|---|---|---|
| Effort to migrate | ~3 weeks | ~2 weeks | 0 |
| Domain alignment | High (built for conversations) | Medium (generic state machine) | High (purpose-built) |
| Voice integration | Native (same family as pipecat) | Custom bridge needed (~1 week) | Already done |
| Text mode | Mini pipeline per HTTP request | First-class | Already done |
| State persistence | FlowManager state + bridge | PostgresSaver + bridge | `SessionEvent` (Rule 9) |
| Resume / replay | Via FlowManager save/restore | Via checkpointer + time-travel | `reconstruct_state(events, outline)` |
| Subgraph / sub-workflow | Dynamic flows (sub-flows) | Native subgraphs | Would need ~200 LOC custom |
| Researcher UI changes | None (server compiles) | None (server compiles) | None |
| LLM call shape | Tool calling (per-slot) | Either (we'd keep structured output) | Structured output |
| DeepSeek tool-call risk | **Medium** — must spike | Low (we keep structured output) | None |
| 2 LLM calls / turn (Rule 4) | Engineer-discipline | Engineer-discipline | Default |
| AI does not decide edges (Rule 12) | Engineer-discipline (rule transitions) | Engineer-discipline (rule edges) | Default |
| Event sourcing (Rule 9) | Bridge required | Bridge required | Native |
| Dependency size | Small (pipecat already vendored) | Large (langchain ecosystem) | None |
| Test survival rate | ~30% | ~50% | 100% |
| Reversibility (rolling back if it doesn't work) | Hard (3-week rewrite to undo) | Hard (2-week rewrite to undo) | N/A |

## Why we're deferring (May 2026 context)

1. **No measured pain.** ADR 0009's list interpreter shipped two days ago. 150 tests pass; live PoC is 49/50; zero internal user has actually run it end-to-end yet (P3.5 dogfood is gated on real participants and voice infra).
2. **One framework swap per quarter is enough.** ADR 0007 → 0009 already cost a week. A second swap before the first one's GA is reckless.
3. **The wins are speculative.** Both frameworks promise nicer abstractions for "complex multi-step questions" — but we haven't yet demonstrated the v2 list interpreter is insufficient for any real research design. Build for measured pain, not imagined pain.
4. **A cheaper increment exists** for the most likely real pain (probe quality, deep extraction): see § Recommended next step.
5. **DeepSeek tool-call reliability is unverified.** pipecat-flows specifically depends on this and we have no data. Until that 1-day spike runs (§ Spike), pipecat-flows is unscored.

## Triggers — when to revisit this ADR

Revisit (and pick a path) when **any two** of the following are true:

1. P3.5 dogfood reveals ≥3 distinct questions where slot extraction + skip_if cannot express the desired interaction (e.g., concept testing with stimuli, longitudinal follow-up branching, participant-led narrative depth).
2. Internal users explicitly ask for time-travel debugging of bad sessions (`reconstruct_state` insufficient).
3. The team grows from 1 engineer on conductor to 3+; maintaining a hand-rolled engine becomes more expensive than picking up a framework.
4. A new requirement lands that the list interpreter cannot satisfy in <1 week of changes (e.g., parallel sub-conversations, multi-modal stimuli orchestration).
5. DeepSeek gets a peer in our stack (e.g., we add Anthropic for analysis), making framework portability worth the cost.

If exactly one trigger fires, ship a v2.x increment instead (§ Recommended next step).

## Spike — DeepSeek tool-call reliability validation

Before committing to **pipecat-flows**, run this 1-day spike:

```python
# merism/conductor_v2/tests/spike_deepseek_tool_calls.py
@pytest.mark.merism_llm_live
def test_deepseek_multi_tool_node():
    """Single node with 5 record functions. Run 50 times. Measure call accuracy."""
    tools = [record_drinks_coffee, record_cups_per_day, record_brew_method,
             record_shop_or_home, record_brand_loyalty]
    fm = FlowManager(...)
    fm.set_node(NodeConfig(task_messages=[...], functions=tools))
    
    metrics = {"correct_tool_calls": 0, "wrong_tool": 0, "no_call": 0, "malformed": 0}
    for case in COFFEE_CASES * 5:
        result = await fm.handle_message(case.reply)
        ...  # classify
    
    # Acceptance: ≥ 47/50 correct (matches v2 baseline)
    assert metrics["correct_tool_calls"] >= 47
```

If the spike passes (≥ 47/50), pipecat-flows is a real option for a future migration. If it fails (< 40/50), pipecat-flows is dead and only LangGraph remains a viable swap target.

LangGraph does not require this spike (we would keep structured output, not tool calling).

## Recommended next step (instead of framework swap)

Ship **v2.1 — Probe Plan protocol field** (~4 days). This addresses the most likely real pain (probe quality / deep extraction) without a framework migration.

Sketch:
- Add optional `QuestionNode.probe_dimensions: list[ProbeDimension]` (each with name, description, completion_signal).
- `ai.extract` returns existing slots + new `dimension_completeness: dict[str, float]` (0.0–1.0 per dimension).
- `ai.generate` for probe receives the lowest-completeness dimension as `focus_dimension` hint; prompt steers the next probe at that dimension.
- Frontend `V2AdvancedSection.tsx` adds a third collapsible block for `probe_dimensions`.
- Backward compatible: questions without `probe_dimensions` behave exactly as v2.0.

If v2.1 + 1–3 internal dogfood sessions still leave gaps, **then** revisit this ADR.

## Open questions (for whoever picks this up)

1. If pipecat-flows is chosen, do we expose the visual flow editor (`flows.pipecat.ai`) to researchers, or keep the list editor and compile invisibly? Recommend: keep list editor; researchers don't write graphs.
2. If LangGraph is chosen, do we keep `SessionEvent` as the event-sourcing root, or migrate to LangGraph's checkpoint table? Recommend: keep `SessionEvent` (it serves analytics + Rule 9), use LangGraph checkpoints only for engine-level resume.
3. Either path: how do we migrate live in-progress v2 sessions on the day of cutover? Recommend: drain (reject new sessions on old engine, finish in-flights, then flip).
4. Either path: do we keep `merism.conductor_v2.engine.run_interview` as a fallback for one release after cutover, or hard-cut? Recommend: keep for one release, behind a `MERISM_V2_ENGINE=legacy` env var, in case framework path has emergent issues.

## References

- ADR 0009 — current architecture (list interpreter)
- `docs/specs/conductor-v2/` — current v2 spec
- `AGENTS.md` Rules 4, 9, 12, 13 — non-negotiable constraints
- pipecat-flows: https://github.com/pipecat-ai/pipecat-flows (BSD-2, v1.1.0 May 2026)
- LangGraph: https://github.com/langchain-ai/langgraph (MIT)
