# ADR 0008 — Bubble segments and inline ClientAction interleaving

Date: 2026-05-22
Status: retired (depended on the DAG block model; superseded by ADR 0009)
Supersedes: —
Refines: ADR 0007 (Conductor v2 Typebot engine)

## Context

Conductor v2 (ADR 0007) adopts Typebot's bot-engine model: AI produces typed slot values and streamed text; flow control is rule-driven. The engine walks a FlowGraph of typed blocks. Researcher-attached stimuli (`Question.linked_stimulus_ids`) are passed to the frontend so the participant sees the right artifact while answering.

Two gaps surface when comparing this model against OpenMAIC's lecture playback engine (`THU-MAIC/OpenMAIC`, `lib/playback/engine.ts`):

1. **No coupling between speech timing and visual cues.** Our `BubbleBlock.text` is opaque to the engine: when TTS plays "你看到这张图后第一感受是什么？", nothing tells the frontend "highlight `stimulus_42` at the word '这张图'". Question text and stimulus display are two parallel tracks; alignment is best-effort timing, not structural.

2. **AI Generate output is a flat stream.** Probe / move_on / clarify text from `AIGenerateBlock` flows to TextChunker → TTS as plain text. Even when the prompt could produce mid-sentence visual cues ("…about brand X [pause to spotlight product X]…"), there is no protocol for the model to emit such cues structurally; they would just be inline parentheticals lost in TTS.

OpenMAIC solves the lecture analog elegantly. A scene's content is `actions: Action[]` — a single ordered sequence interleaving `speech`, `spotlight`, `wb_draw_*`, `discussion`. The playback engine executes them sequentially: `speech` blocks until TTS `onEnded`, `spotlight` is fire-and-forget. Speech-visual sync is a natural byproduct of the sequence — the spotlight fires immediately after the relevant utterance because that's where it sits in the array.

That mechanism does not generalize to the interview problem (lectures are one-way; interviews are bidirectional with branching). But the **micro-level sequencing pattern within a single utterance** does transfer cleanly:

- A Bubble block can become a sequence of speech sub-units interleaved with client-side actions.
- An AI Generate block can emit inline action markers in its streaming output, which a parser strips from TTS-bound text and converts to ClientAction emits.

ER11 (Client Actions Protocol) already defines the `ClientAction` shape and `pending_client_actions` queue, but currently emits only at concept-rotation boundaries (`merism.conductor_v2.engine` calls `_emit_stimulus_show` when `typebots_queue` rotates). The protocol exists; only the in-block emit paths are missing.

## Decision

Extend `BubbleBlock` and `AIGenerateBlock` to support **inline interleaving of speech and ClientAction**, mirroring OpenMAIC's `Action[]` ordering pattern at the block level. ClientAction remains a v2.0 primitive (ER11, currently `stimulus_show` only); this ADR adds two emit paths but does not introduce new action types.

Concretely:

1. **`BubbleBlock.segments`** — a new optional field of type `list[BubbleSegment]` where each segment is a discriminated union of `SpeakSegment(text)` and `ClientActionSegment(action)`. Engine executes segments in array order; speak segments await TTS playback (matching OpenMAIC's `audioPlayer.onEnded → next`), action segments are fire-and-forget (matching OpenMAIC's `spotlight` semantics). At most one of `text` (legacy) / `segments` / `variable_id` (`dynamic_ref`) is set per block.

2. **`AIGenerateBlock.allow_inline_actions: bool`** — when true, the streaming output is parsed for `[[action:type:payload_json]]` markers (Typebot/OpenMAIC-style `parseStructuredChunk`). Markers are stripped from the TTS-bound text and emitted as ClientActions at the position they occur in the stream. The AI Generate prompt template gets a compiler-injected suffix listing available action types and the marker syntax. Default `false` for back-compat — only opt-in blocks parse markers.

3. **Compiler synthesizes segments from `Question.linked_stimulus_ids`.** When a question has stimuli attached, the compiler emits the question's BubbleBlock as `segments=[ClientActionSegment(stimulus_show), SpeakSegment(question_text)]` instead of a flat `text`. Researchers do not write segments by hand; they keep editing one text field plus an attach-stimulus picker. Phase 2 compiler (`merism.conductor_v2.compiler`) gains the `_compile_question_segments` helper.

4. **VoiceConsumer dispatches segments in order.** The voice runtime already drains `state.pending_client_actions` to the WebSocket on block exit. For segments, it drains *between* speak-segment TTS playbacks: the next speak segment starts only after the previous one's `onPlaybackFinished` fires (ER13), and any `ClientActionSegment` that sits between them is dispatched before the next speak begins. This produces deterministic speech-visual ordering without runtime alignment code.

5. **Round-trip stays byte-identical.** Decompiler reads `segments`; if a Bubble's segments are a single `SpeakSegment` and the question has no stimuli, decompile back to the legacy `text` form. If segments are mixed, the decompiler synthesizes a normalized outline question carrying `linked_stimulus_ids` plus the speech text. Compile-decompile-compile remains byte-identical for any outline the compiler can produce.

The protocol surface is **strictly additive**. v1 sessions keep working; v2 sessions with the legacy `text`-only Bubble keep working; only blocks the compiler chooses to emit as `segments` engage the new path.

AGENTS.md Rule 4 (2 LLM calls per turn) is unaffected — segments and inline action markers are pure data; no extra LLM calls.

AGENTS.md Rule 9 (event sourcing) is preserved by emitting one event per segment processed:

- `bubble_segment_executed` — `{block_id, segment_index, kind: "speak" | "action"}`
- `client_action_emitted` already exists (ER11)

State reconstruction folds segment events into the same `current_block_id` advancement; partial-Bubble interruption is replayable.

## Consequences

### Positive

- Stimuli land at the right moment in the question utterance; the participant hears "这张图" while seeing the image highlighted, not 800ms before or after.
- Probe / move_on AI Generate can emit per-utterance cues (spotlight a product, reveal a follow-up image, push a chart) without inventing a new sub-protocol — markers parse to existing ClientActions.
- Compiler determinism extends: researchers' attached stimuli become structural in the FlowGraph, not handed off as a side-channel `linked_stimulus_ids` array the engine ignores.
- Static audit improves: opening a compiled FlowGraph in the read-only graph view shows exactly which segment fires which action, so researchers can see "AI will spotlight the product when it says 'this'."
- Pattern transfer from OpenMAIC is contained — we adopt the sequencing primitive, not the lecture-shaped scene model. v2's bidirectional, branched topology stays intact.

### Negative

- Net new schema fields (`BubbleBlock.segments`, `AIGenerateBlock.allow_inline_actions`) and a new `BubbleSegment` discriminated union. Phase 2 compiler / decompiler / engine all gain a code path. Estimated +400 LOC core, +200 LOC tests.
- Inline action markers in AI Generate output are model-prompt-engineered, not enforced. A misbehaving model could emit malformed `[[action:...]]` strings that escape into TTS. Mitigation: parser falls open (treat unrecognized markers as literal text) and logs `inline_action_parse_failed`; the marker is *never* spoken because we strip the entire bracketed segment up to the closing `]]`.
- Voice consumer must coordinate TTS playback boundaries with action emit. Currently it dispatches actions on block exit; segment-aware dispatch needs a per-segment `await playback_finished` step. This is the same pattern as OpenMAIC's `audioPlayer.onEnded → next`, so the implementation is well-trodden, but it adds a state-machine wrinkle in `merism.realtime.voice`.
- Round-trip identity becomes harder to prove when segments contain non-trivial mixes. We keep the strong claim only for compiler-produced graphs; researcher edits to segments by hand (which we forbid in v2) would break the property. Documented as a v2-era hard constraint: researchers edit outline + stimuli, never segments.

### Neutral

- ClientAction protocol (ER11) gains real users; previously only emitted at concept rotation. The `stimulus_show` schema is exercised more, but not extended.
- TextChunker stays the canonical phrase-level chunker; the inline-action parser sits *upstream* of it, in `AIGenerateBlock` execution. Markers are removed before chunks reach TTS.

## Alternatives Considered

### A. Keep `BubbleBlock.text` flat; rely on frontend timing heuristics

Rejected. This is the status quo and the gap we identified. Frontends timing image displays against TTS playback start (or against fixed character offsets) is fragile across STT/TTS providers and locales. Speech rate varies; CJK characters tokenize differently than Latin words. Any heuristic would need re-tuning per voice and per language.

### B. Add `BubbleBlock.stimulus_id` as a single-stimulus shortcut, no segments

Rejected as insufficient. It handles the common case of "show one image with one question" but not the realistic compounds:
- Two-stimulus comparison ("look at both products and tell me which feels heavier") — needs two stimulus_show actions in sequence.
- Stimulus that should appear *during* speech, not before — needs ordering between segments.
- AI Generate's runtime cues — orthogonal to the per-block field.

A shortcut field would also fragment the protocol: BubbleBlock would carry an action shape that isn't reusable for AI Generate's needs.

### C. Adopt OpenMAIC's `Scene { actions: Action[] }` model wholesale

Rejected. OpenMAIC's scene-level Action[] is a flat sequence with no branching — appropriate for one-way lectures, structurally wrong for branched interviews. We have:
- Multiple block types per group (Bubble + Input + AIExtract + Condition + ...) tied together by edges.
- Branching at every Condition.
- Sub-flows for concept rotation.
- Side-trips via Jump+Return.

Forcing all of these into one `actions: Action[]` array would either flatten the branching (loses interview value) or invent a new "control flow action" subtype that recreates the FlowGraph inside the array (more complex, not less).

The right scope is to borrow the **per-block sequencing pattern** within Bubble and AI Generate, where it makes sense, while leaving the FlowGraph in charge of cross-block control flow.

### D. Defer; ship v2 GA without this and add later

Rejected for now (still time before GA), accepted as the implementation order: this ADR is **proposed**, not blocking GA. Phase 2 ships with ER1-ER15 only. ER16 lands as a Phase 2.5 increment after Phase 3 dogfood reveals whether stimuli-during-speech is a real friction point in real interviews. The ADR is written now so the schema migration is not a surprise to the editor or replay UI.

## Implementation Plan (R26+ Phase 2.5)

Tracked separately as `tasks.md` Phase 2.5 (to be added when ADR is **accepted**):

1. **P2.5.1**: Schema additions to `merism/conductor_v2/schema.py` (`BubbleSegment`, `SpeakSegment`, `ClientActionSegment`, `BubbleBlock.segments`, `AIGenerateBlock.allow_inline_actions`). Backward compat via discriminated nullability.
2. **P2.5.2**: Inline action marker parser in `merism/conductor_v2/inline_action_parser.py` — recognizes `[[action:type:payload_json]]`, strips from text stream, returns parsed actions in stream order.
3. **P2.5.3**: Engine segment executor in `merism/conductor_v2/engine.py` — `execute_bubble_block` recognizes `segments` and walks them; `execute_ai_generate_block` runs the parser when `allow_inline_actions=True`.
4. **P2.5.4**: Compiler synthesis in `merism/conductor_v2/compiler.py` — `_compile_question_segments` produces `BubbleBlock(segments=...)` when `Question.linked_stimulus_ids` is non-empty.
5. **P2.5.5**: Decompiler in `merism/conductor_v2/decompiler.py` — recognize segments, recover `linked_stimulus_ids` + question text. Round-trip identity test added to `test_decompiler.py`.
6. **P2.5.6**: VoiceConsumer segment-aware dispatch in `merism/realtime/voice.py` — `await playback_finished` between speak segments; client action segments pushed in-order on the WebSocket via existing `StimulusShowMessage` (no protocol change).
7. **P2.5.7**: AI Generate prompt suffix in `merism/conductor_v2/prompts/inline_actions.py` — describes the marker syntax + currently allowed action types, injected into AI Generate templates that opt into `allow_inline_actions=True`.

## References

- ADR 0007 — Conductor v2 Typebot engine
- ER11 (`docs/specs/conductor-v2/design.md`) — Client Actions Protocol
- ER13 (`docs/specs/conductor-v2/design.md`) — WS-Level Hard Timeout (PlaybackFinishedMessage protocol)
- OpenMAIC `lib/playback/engine.ts` — Action[] sequential execution
- OpenMAIC `lib/orchestration/stateless-generate.ts` (`parseStructuredChunk`) — inline action marker parsing
