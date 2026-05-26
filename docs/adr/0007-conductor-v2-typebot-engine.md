# ADR 0007 — Adopt Typebot bot-engine model for Conductor v2

Date: 2026-05-22
Status: superseded by ADR 0009 (2026-05-22 same day, before any production traffic)
Supersedes: —

## Context

The current interview moderator is `merism.conductor.moderator.stream_turn`, a 2-node pipeline (`coverage_steer` → `decision_validator` → `generate`). For each user turn:

1. `coverage_steer` (non-streaming LLM call) returns a `ModeratorDecision` choosing one of `{followup, move_on, clarify, close}` plus a `next_question_id`.
2. `decision_validator` enforces three hard rules (probe_policy, max_probes, dynamic_probe budget) and may rewrite the decision.
3. `generate` (streaming LLM call) renders the spoken reply.

This shape is correct in skeleton but stops short of "engineering the AI out of flow control." The validator rules are a thin server-side seatbelt; everything subjective ("did the participant answer adequately?", "is this answer shallow?", "should we probe expansion or clarification?") still lives inside `coverage_steer`'s prompt and LLM judgment. Validated against ~30 real interviews:

- LLM has a strong "推进感" prior — it `move_on`s prematurely on shallow but on-topic answers.
- "trigger=vague / shallow / factual_only" is interpreted differently across runs (T=0.2 still wobbles).
- Coverage is judged by the LLM's gut feel on `recent_turns + coverage_context`; gaps are only detected in aggregate (CoverageSnapshot, post-session), not in-session.
- A single `next_action` cannot represent multi-intent participant turns (refusal + topic-switch + spontaneous q3 answer in one utterance).
- Decisions are only retroactively explainable via `think_notes` — researchers cannot audit "why did the AI move on" reliably.

`docs/research/execution-engine-research.md` (2026-05-21) compared Typebot, Rasa, and the current Merism model. Conclusion: the current model has more determinism than the research initially credited, but the **subjective LLM judgments at the heart of `coverage_steer` are the ceiling**. Continuing to tune prompts will not break through.

## Decision

Replace `merism.conductor` (the moderator runtime) with a new engine modeled after Typebot's `bot-engine`. Core design move: **AI is content-only; flow is rule-driven**.

The new engine, **Conductor v2** (`merism.conductor_v2`), has these properties:

1. **Flow is a graph of typed blocks.** A study guide compiles into a `FlowGraph = {groups, blocks, edges, variables, events}`. Block types: `Bubble` (output), `Input` (wait for participant), `Logic` (Condition / Jump / SetVariable), `Integration` (AI Extract / HTTP).
2. **Decisions are Conditions on typed variables.** Whether to probe, skip, or move on is a Condition block evaluating a `Variable` populated by an `AI Extract` block. The LLM does not return `next_action`; it returns *typed slot values*. Slot validation is `is_set` / `equals` / `array_min_size` — no LLM in the loop.
3. **AI is exactly two block types.** `AI Extract` (structured slot extraction via JSON Schema) and `AI Generate` (streaming text for Bubble content). LLM never selects edges. Two LLM calls per turn — same shape as today, AGENTS.md Rule 4 unchanged.
4. **Each turn is a `walk_flow_forward` loop.** Engine walks: dequeue edge → enter group → execute blocks → on `Input`, stop and emit; on `Logic`, evaluate and pick outgoing edge; on `Integration`, call AI / HTTP and store result. Pure, deterministic.
5. **Researcher writes a list, engine sees a graph.** The outline editor stays list-based. Each list item compiles to a `QuestionGroup` macro: 1 Bubble + 1 Input + 1 AI-Extract + 1-2 Conditions + 1 probe-loop subgroup. Researchers never see edges.
6. **Exception handling is structural.** `ParsedReply` returns three states (`success` / `fail` / `skip`); `InvalidReplyEvent` jumps to a configured edge with `returnMark` resume; `CommandEvent` handles user intents; `ReplyEvent` runs side-effect hooks. Borrowed wholesale from Typebot.
7. **Concept rotation uses sub-flow queue.** `typebotsQueue`-style stack handles per-concept expansion, replacing the ad-hoc `expand_guide` in `concept_plan.py`.
8. **Idle/silence handling is silent.** Push-to-talk idle thresholds are observed and recorded as `SessionEvent.kind = silence_observed`, but **no audible or visible feedback** is produced — no backchannel TTS, no caption hints, no UI nudges. Only the hard `T4` ceiling produces a state transition (`session.status = interrupted`). Researcher dashboards consume the silence events for replay analysis.

## Consequences

### Positive

- Researcher's intent (`required_slots`, `skip_if`, `max_probes`) becomes an enforceable contract. Audit is a graph traversal, not LLM introspection.
- LLM behavior cannot drift across runs in flow control — only in content generation, where drift is acceptable.
- All exception cases (refusal / evasion / off-topic / silence / wrong-format / command) compose from the same primitives instead of bespoke handling.
- Same 2-LLM-call shape per turn → first-token latency budget unchanged.
- Concept rotation simplifies (engine native sub-flow vs. manual expansion).

### Negative

- Significant rewrite: ~80% of `merism/conductor` is replaced; `state.py`, `decision_prompt.py`, `decision_validator.py`, `guide_cursor.py`, `concept_plan.py` either deleted or radically rewritten.
- `InterviewGuide.sections` JSON schema migrates from a list-of-questions shape to a `FlowGraph` shape. Old sessions sealed against old schema; new sessions go to v2.
- Researchers must declare `required_slots` per question. Mitigated by AI-drafted slot schemas in the outline review pass.
- Outline-list ↔ FlowGraph compiler is new high-stakes code: bugs there are silent (flow runs the wrong shape and researcher does not see).

### Neutral

- AGENTS.md Rule 4 (2-node moderator, 2 LLM calls per turn) preserved by reframing: extract + generate are the two nodes.
- AGENTS.md Rule 9 (event sourcing) preserved and extended with new event kinds: `block_entered`, `edge_traversed`, `variable_set`, `return_mark_set`, `return_mark_consumed`, `command_received`, `invalid_reply`, `silence_observed`, `timeout`.
- Trace_id binding (Rule 10) unaffected.

## Alternatives Considered

### A. Incrementally tighten `coverage_steer` prompts + add more validator rules

Rejected. The ~30-interview review showed prompt refinement plateaued; the failure modes (premature move_on, subjective trigger judgment, multi-intent turns) are structural, not lexical.

### B. Rasa-style declarative Form (slot-fill loop)

Rejected. Rasa's `is_done = all slots filled` is binary. Our value is judging answer *depth*, which an LLM-extracted slot with a confidence score handles better than a YAML required-list. We borrow Rasa's slot-as-first-class-citizen idea, not its control loop.

### C. Build a custom DAG runtime from scratch

Rejected. Typebot already runs at scale with a 5-block / edge / variable model that fits 95% of our needs. Reinventing is waste; delta is small (block-level timeout, max_retries, command intent classifier).

### D. Adopt Typebot as a runtime dependency

Rejected. It is TypeScript; our backend is Python. The engine is ~600 lines of core algorithm. A Python port (with our own primitives) is cheaper than a TS-Python bridge, and avoids an additional process / IPC boundary in the audio hot path.

## Notes on Silent Idle Handling (PTT Mode)

Push-to-talk interview mode introduces a real-time concern Typebot does not address: the participant may pause for 5–90 seconds while thinking. Earlier drafts of this design proposed audible "嗯，你慢慢想" backchannel TTS at a medium threshold and a "你还在吗" prompt at a heavy threshold. **These are explicitly out of scope.** Conductor v2:

- **Records** silence events at four thresholds (T1 / T2 / T3 / T4). Default values: 12s / 30s / 90s / 240s, configurable per question via `silence_policy`.
- **Emits no audio**, no caption text, no UI hint at any threshold.
- **Only T4** triggers a state transition: `session.status = interrupted` and the WebSocket halts accepting further input. This is necessary so sessions do not pin compute resources indefinitely.
- T1 / T2 / T3 are pure observability: the events feed researcher dashboards (replay timing analysis, "this participant paused 90 s on q5") and may inform future automated quality scoring.

Speech-too-long handling (participant holds PTT past STT's safe window) is handled via internal soft-finalize at ~30s — the utterance is segmented into multiple turns, but **no user-visible marker is shown**. From the participant's perspective the experience is continuous.

Rationale: real interviewers exhibit minimal-but-careful silence behavior; novice AI behavior here is high-risk. Until we have ≥100 interviews of replay data, we observe and analyze before producing any user-facing silence feedback.

## References

- `docs/research/execution-engine-research.md` (2026-05-21)
- `docs/specs/conductor-v2/{requirements,design,tasks}.md`
- Typebot bot-engine reference (`packages/bot-engine/src/walkFlowForward.ts`)
- ADR 0006 (event log foundation, preserved by v2)
- AGENTS.md Rules 4, 9, 10
