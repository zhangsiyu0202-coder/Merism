# ADR 0009 — Replace Conductor v2 DAG runtime with a list interpreter

Date: 2026-05-22
Status: superseded by ADR 0012 (2026-05-23)
Supersedes: ADR 0007 (Conductor v2 Typebot DAG engine), ADR 0008 (Bubble segments — drafted against the DAG model, retired with it)

## Context

ADR 0007 adopted Typebot's DAG-shaped bot-engine for Conductor v2: every interview compiles to a `FlowGraph` of typed `Block` nodes connected by `Edge` arrows, and the engine walks that graph turn by turn. The compiler explodes a researcher-authored question list into ~7 blocks + 8 edges per question, plus 8 ER12 global groups, plus virtual edges, plus the `typebotsQueue` sub-flow stack. A reverse compiler (`decompiler.py`) reconstructs the question list whenever the editor reopens the study.

Phase 0 / 1 / 2 implementation made the architecture concrete:

- `compiler.py` — 1135 LOC after the recent minimalism pass
- `engine.py` (`walk_flow_forward`, block executors) — ~910 LOC
- `schema.py` (`FlowGraph` / `Block` discriminated union / `Edge` / `SessionState`) — ~700 LOC
- supporting helpers (`condition.py`, `virtual_edge.py`, `dummy_block.py`, `starting_point.py`, `get_next_block.py`, `sub_flow.py`, `event_log.py`, `persistence.py`, `events.py`, `set_variable_eval.py`, `variables.py`, `types.py`) — another ~1200 LOC combined
- 357 tests across `merism/conductor_v2/tests/`

That stack works — Phase 0 PoC validated AI Extract stability + path accuracy against live DeepSeek / Qwen calls. Tests are green. The architecture is internally consistent.

But it earns very little of its complexity. Reviewing the actual usage shapes after Phase 2 implementation:

1. **The macro topology is linear.** Every researcher writes a question list. The compiler produces edges that only run forward (`q1 → q2 → q3 → ...`) plus rare skip-if jumps. Multi-incoming edges, loops at the macro level, and arbitrary cross-question structures never appear.
2. **The micro topology is one repeated state machine.** Every QuestionGroup compiles to exactly the same shape: `Bubble → Input → AIExtract → Decision[3 items + default] → maybe Probe[Guard → Inc → Generate → loop]`. The DAG just stores this fixed shape ~N times.
3. **Researchers don't author graphs.** Typebot's DAG fits Typebot because Typebot users connect blocks on a canvas. We have no canvas. The "open the flow graph view" feature was never a researcher entry point — it is a debug surface.
4. **The compiler is a tax, not a value-add.** `compile_outline` produces a graph; `decompile_outline` immediately reverses it for the editor. The two functions exist purely to let the engine pretend it works on graphs. Round-trip identity (compile → decompile → compile = byte-identical) is a property we maintain, not one we use.
5. **The "AI is content-only, flow is rule-driven" contract from ADR 0007 is preserved by the data, not by the DAG.** The LLM produces typed slot values. Routing decisions read those slot values. Expressing the routing as "ConditionBlock with 14 operators evaluating Variable references" vs. "Python `if` over a slot dict" gives the same expressivity. Typebot's 14-operator condition algebra exists because Typebot lets researchers compose conditions in the canvas; we never expose that algebra to researchers (`skip_if` is editor-modeled as one operator + value).

The cost is real:

- ~3000 LOC of compiler / engine / schema / helpers to maintain
- An order-of-magnitude more SessionEvent kinds (`block_entered`, `edge_traversed`, `variable_set`, plus the rest) than researchers actually inspect
- Cognitive overhead for new contributors — the question "where does refusal handling live?" routes through `_decision_items` → `e_decision_refused` → `g_on_refusal_default` group → ReturnBlock semantics → returnMark stack semantics. Nothing about an interview moderator is intrinsically that layered.
- Schema drift risk during the v2 → GA path

Conductor v2 has not shipped to production yet. There is no live data to migrate, no in-flight session whose `moderator_state` has the v2 DAG shape. This is the cheapest moment to revisit the architecture.

The product reality is: **researchers write a list of questions; the engine asks them in order; for each question it loops on probes until slots are filled or the budget is spent; rules like skip-if jump within the list**. That is a list interpreter, not a graph traversal.

## Decision

Replace the DAG runtime with a **list interpreter** at the conductor v2 layer. The persisted artifact for an interview guide is the researcher-authored list of questions itself — no compile step, no FlowGraph, no Block / Edge schema. The engine iterates the list and, per question, runs an inline state machine in plain Python.

Reuse the `merism/conductor_v2/` namespace. ADR 0007's "v2" name now refers to this list interpreter; the DAG implementation is archived in git history. No production code paths broke because v2 was never live.

### Data model

```python
# merism/conductor_v2/schema.py — full v2 schema, ~150 LOC instead of 700

class SlotSchema(BaseModel):
    """One typed slot AI Extract should fill from the participant's reply."""
    model_config = ConfigDict(extra="forbid")
    name: str
    type: Literal["string", "number", "boolean", "array", "enum"]
    description: str = ""
    enum_values: list[str] | None = None
    is_required: bool = True


class SkipIfRule(BaseModel):
    """Skip to another question when a slot value matches."""
    model_config = ConfigDict(extra="forbid")
    when: ComparisonRule  # variable_name + operator + value
    jump_to: str          # question id


class QuestionNode(BaseModel):
    """One interview question. The atomic unit of the outline."""
    model_config = ConfigDict(extra="forbid")
    id: str
    text: str
    intent: str = ""
    required_slots: list[SlotSchema] = []
    skip_if: SkipIfRule | None = None
    max_probes: int = 2
    linked_stimulus_ids: list[str] = []


class Outline(BaseModel):
    """The complete interview guide. Persisted in InterviewGuide.sections.

    Researchers can group questions into sections for editor display, but
    the engine sees a flat list — sections are cosmetic.
    """
    model_config = ConfigDict(extra="forbid")
    version: Literal["v2"] = "v2"
    sections: list[Section] = []  # [{id, title, questions: [QuestionNode]}]
    warmup_text: str = "你好，欢迎参加本次访谈..."
    closing_text: str = "今天的问题就到这里，感谢你的分享。"


class SessionState(BaseModel):
    """Per-session runtime state. Persisted in InterviewSession.moderator_state."""
    model_config = ConfigDict(extra="forbid")
    version: Literal["v2"] = "v2"
    current_question_id: str | None = None
    slot_values: dict[str, dict[str, Any]] = {}  # {qid: {slot_name: value}}
    probe_counts: dict[str, int] = {}            # {qid: count}
    answers: list[Answer] = []                   # successful Input replies
    started_at_epoch: float = 0.0
    completed: bool = False
```

No FlowGraph. No Block. No Edge. No Variable indirection. Slot values live in a flat dict keyed by question id.

### Engine

```python
# merism/conductor_v2/engine.py — entire engine, ~150 LOC

async def run_interview(
    outline: Outline,
    state: SessionState,
    *,
    ai: AIAdapter,
    sink: OutputSink,
    event_sink: EventSink,
) -> SessionState:
    """Drive an interview from current_question_id to closing.

    Pure function of (outline, state, ai, sink) — caller owns persistence.
    """
    questions = flatten_questions(outline)
    if not state.current_question_id:
        await play_warmup(outline, sink, event_sink)
        state = state.model_copy(update={"current_question_id": questions[0].id})

    while not state.completed:
        node = find_question(questions, state.current_question_id)
        if node is None:
            break  # reached end of list
        result = await execute_question(node, state, ai=ai, sink=sink, event_sink=event_sink)
        state = apply_result(state, result, questions)

    await play_closing(outline, sink, event_sink)
    return state.model_copy(update={"completed": True})


async def execute_question(
    node: QuestionNode,
    state: SessionState,
    *,
    ai: AIAdapter,
    sink: OutputSink,
    event_sink: EventSink,
) -> QuestionResult:
    """One question's state machine. Pure Python; no graph traversal."""
    await event_sink.emit("question_entered", {"question_id": node.id})
    await sink.speak(node.text)

    while True:
        reply = await sink.wait_input()
        slots = await ai.extract(reply, node.required_slots, behavior_slots=BEHAVIOR_SLOTS)
        await event_sink.emit("slots_extracted", {"question_id": node.id, "slots": slots})
        merged = merge_slots(state.slot_values.get(node.id, {}), slots)

        if node.skip_if and matches_skip_if(node.skip_if, merged):
            return QuestionResult(skip_to=node.skip_if.jump_to, slots=merged)

        missing = [s for s in node.required_slots if s.is_required and not is_set(merged, s.name)]
        if not missing:
            return QuestionResult(slots=merged)

        probe_count = state.probe_counts.get(node.id, 0)
        if probe_count >= node.max_probes:
            return QuestionResult(slots=merged, gave_up=True)

        prompt = build_probe_prompt(node, missing, merged, recent_turns(state))
        probe_text = await ai.generate(prompt)
        await event_sink.emit("probe_started", {"question_id": node.id, "probe_count": probe_count + 1})
        await sink.speak(probe_text)
        state = state.model_copy(update={
            "probe_counts": {**state.probe_counts, node.id: probe_count + 1},
            "slot_values": {**state.slot_values, node.id: merged},
        })
```

The probe loop, the decision logic, the skip-if rule, and the budget cap are now plain Python within the function body. The slot data is read off `node.required_slots` (researcher-declared). The probe content is generated by AI from the missing-slots data — same data-driven prompt construction the DAG version did, just with the runtime now able to compute `missing_slots` precisely instead of injecting all slots into a static prompt template and asking the LLM to figure out which are missing.

### AI adapter

```python
class AIAdapter(Protocol):
    async def extract(
        self,
        reply: str,
        slots: list[SlotSchema],
        *,
        behavior_slots: list[BehaviorSlotDef],
    ) -> dict[str, Any]: ...

    async def generate(self, prompt: str, *, max_tokens: int = 120) -> str: ...
```

`merism/conductor_v2/ai_clients.py` already implements this surface against DeepSeek and Qwen-Turbo (Phase 0 PoC). The adapter survives the rewrite unchanged — it's the one piece of the conductor_v2 stack genuinely independent of graph vs. list shape.

### Output sink

```python
class OutputSink(Protocol):
    async def speak(self, text: str) -> None: ...        # awaits TTS playback finished
    async def wait_input(self) -> str: ...               # awaits final transcript
```

The voice consumer implements `OutputSink` against the WebSocket; text mode implements it against the SSE stream. Engine never imports either.

### Event log

Reduced to ~6 SessionEvent kinds:

- `question_entered` — `{question_id}`
- `slots_extracted` — `{question_id, slots: {...}}`
- `probe_started` — `{question_id, probe_count}`
- `silence_observed` — `{elapsed_ms}` (60s PTT idle, soft skip path)
- `session_completed` — `{completed_question_ids: [...]}`
- `session_interrupted` — `{cause}` (manual hangup, WS error)

Replayability via folding the event stream over `SessionState` is preserved. The event surface is dramatically smaller because we no longer model every block traversal.

### Persistence

`InterviewGuide.sections` stores the `Outline` JSON directly:

```json
{
  "version": "v2",
  "sections": [
    {"id": "s1", "title": "Coffee", "questions": [
      {"id": "q1", "text": "你平时怎么选购咖啡？", "max_probes": 2, "required_slots": [...]},
      ...
    ]}
  ],
  "warmup_text": "...",
  "closing_text": "..."
}
```

No compile step. The editor's outline shape == the engine's input shape. Round-trip is the JSON serialiser, period.

`InterviewSession.moderator_state` stores `SessionState`. Loadable on resume.

### What's kept

These modules don't depend on engine shape; they survive the rewrite untouched:

- `ai_clients.py` — LLM adapters
- `prompts/behavior_slots.py` — behavior-slot definitions data
- `render_prompt.py` — `{{var}}` placeholder substitution (used by probe prompt builder)
- `sanitize.py` — lone-surrogate / control-char defang
- `parse_input.py` — input validation, simplified to return `str | None` instead of full ParsedReply

### What's deleted

- `schema.py` (replaced)
- `engine.py` (replaced)
- `compiler.py`, `decompiler.py`, `save_path.py` (no compile / decompile step)
- `condition.py` (use Python `if`)
- `virtual_edge.py`, `dummy_block.py`, `starting_point.py`, `get_next_block.py` (DAG plumbing)
- `sub_flow.py` (concept rotation handled at outline level: outer iteration over (concept, list))
- `events.py` (no InvalidReply / Command / Reply event handlers — those are voice-consumer concerns now, not engine concerns)
- `set_variable_eval.py` (no SetVariableBlock)
- `variables.py` (slot values are a plain dict)
- `types.py` (replaced)
- `event_log.py` (replaced with simpler version)
- `persistence.py` (replaced; just JSON dump/load)
- All corresponding `tests/test_*.py` for the above
- ADR 0008 (Bubble segments) — was an extension of the DAG schema; not directly portable. The underlying need (speech ↔ stimulus sync) returns as a phase-3 design problem at the OutputSink layer if Phase 3 dogfood reveals the gap.

## Consequences

### Positive

- Engine becomes ~150 LOC of plain Python instead of ~3000 LOC of compiler + graph runtime
- Researcher mental model and engine input model are identical: a list of questions
- Probe behavior gets cleaner — runtime knows exactly which slots are missing, can construct precise probe prompts
- New contributors read `execute_question` and understand the entire interview lifecycle in one screen
- Event log shrinks to events researchers actually inspect during replay
- `InterviewGuide.sections` becomes inspectable / editable JSON; no need for "decompile to re-open" flow
- API simplifies: no `outline_compile_preview` endpoint, no `compilation_errors` 422 path, no version ratcheting on every minor edit (we still bump version on save, but the saved shape is stable)
- Cuts ~3000 LOC of code we just wrote and ~3500 LOC of tests that exist to verify the cut code's correctness

### Negative

- ~3 days of focused work to rewrite (offsetting the savings)
- ADR 0007 supersession is real — anyone reading the codebase after this point has to understand v2-A (DAG) was a dead branch
- `condition.py`'s 14-operator algebra was a real piece of expressivity. We lose the ability for researchers to express compound conditions like "skip if (slot_a contains "yes" AND slot_b is_set)". For now `skip_if` only supports single-operator rules. If we ever need compound rules, we revisit — but Typebot DAG users compose multi-rule edges visually, which we don't support in the editor anyway, so the expressivity was theoretical
- Concept rotation moves from engine-internal `typebotsQueue` to outer iteration in `run_interview` — slight refactor cost when concept testing studies arrive. Acceptable; concept testing is a Phase 4+ feature
- ADR 0008's bubble-segments / inline-action design was tied to the DAG block model. The product need (sync stimulus to question speech) returns as a Phase 3 design issue with cleaner solutions in the new model

### Neutral

- AGENTS.md Rule 4 (2 LLM calls per turn — extract + generate) preserved verbatim. The list interpreter still calls `ai.extract` then `ai.generate`. No engine-level model change
- AGENTS.md Rule 9 (event sourcing authoritative) preserved. Event kinds are fewer but state reconstruction from events still works
- Trace_id binding (Rule 10) preserved
- LLM stack (DeepSeek + Qwen, Rule 5) unchanged
- Phase 0 PoC results carry over — the AI Extract stability / latency measurements are about the LLM call, not the surrounding engine

## Migration

Conductor v2 has not shipped to production. There are no live sessions in v2 DAG shape, no `InterviewGuide` rows with `sections.version == "v2"` (the dual-engine routing key from AGENTS.md Rule 13 was prepared but never tripped because no v2 sessions exist).

Migration steps:

1. Land this ADR + new requirements / design / tasks docs.
2. Delete the DAG-era code listed above.
3. Land the new `schema.py` + `engine.py` + tests.
4. Update `merism/api/views.py` outline endpoints — drop compile preview, simplify save/load to JSON pass-through.
5. Update frontend `outline/types.ts` + `outlineEditorLogic.ts` — minor cleanup since the editor was already list-shaped.
6. Run full test + lint + typecheck suite.
7. Leave Phase 0 PoC fixture (`tests/fixtures/poc_coffee_question.py`) in place but rewrite it against the new schema — the 10 cases + 5 reruns evaluation is still the architectural validation we depend on for "AI Extract is stable enough."

v1 conductor (`merism/conductor/`) and the dual-engine routing rule (Rule 13) are unaffected. v1 stays the live moderator until v2 GA, same as before.

## Alternatives Considered

### A. Keep the DAG, ship Phase 2 GA, revisit later

Rejected. Phase 2 GA would tie us to the DAG schema for the 6-week grace period (Rule 13), and v3 migration would then mean migrating live sessions — much more expensive than a pre-GA rewrite. The cheapest moment to fix this is now.

### B. Build a list interpreter alongside DAG, route per study type

Rejected. Two parallel engine paths, two persistence shapes, two test suites. The dual-engine cost compounds without earning anything — the DAG path's flexibility never gets exercised.

### C. Keep the DAG schema as the persistence format but write a "fast path" interpreter for simple cases

Rejected. The persistence format is the long-term constraint. If we keep the DAG schema, we still pay the schema complexity tax in the editor, the API, the migration story. The win from cutting it is mostly in the schema, not in the runtime.

### D. Adopt a graph library (e.g. NetworkX) for the DAG to reduce custom code

Rejected — the graph library wraps a problem we don't have. We don't need graph algorithms; we need to ask 10 questions in order with skip-if jumps.

## References

- ADR 0007 — Conductor v2 Typebot DAG engine (now superseded)
- ADR 0008 — Bubble segments + inline ClientAction (retired with the DAG)
- `docs/specs/conductor-v2/poc_results.md` — Phase 0 PoC evaluation (still valid for the AI extract layer)
- AGENTS.md Rule 4, Rule 9, Rule 13
