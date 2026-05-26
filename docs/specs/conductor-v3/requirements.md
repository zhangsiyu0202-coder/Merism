# Conductor v3 — Requirements

> Replaces conductor v1 (`merism.conductor.moderator`) and the deleted v2 (list interpreter).
> Supersedes ADR 0009 (list interpreter). Scope deliberately reset: ADR 0012 (this spec) keeps two and only two capabilities — strict outline traversal and dynamic follow-up.

EARS-style. Each clause is testable.

---

## 1. Goal (one sentence)

Drive an interview that **strictly traverses a researcher-defined outline** and **dynamically probes when the researcher requests it**, on top of LangGraph (`StateGraph`).

Everything not serving these two goals is out of scope. v2's typed slot extraction, skip_if jumps, behavior-slot taxonomy (refused/evasive/off_topic/...), event sourcing per-turn — all dropped.

---

## 2. Outline shape (Req 1–4)

**Req 1**: An outline is a list of sections. Each section is a list of questions. The system **shall** persist the outline as JSONB on `InterviewGuide.sections` with the top-level shape `{"version": "v3", "sections": [...]}`. The `version` literal is the dual-engine routing key (Rule 13).

**Req 2**: Each question **shall** have exactly five required fields and one optional field:

| Field | Type | Required | Purpose |
|---|---|---|---|
| `id` | string | yes | stable identifier, used for transcript + skip_if (future) |
| `ask` | string | yes | the question the moderator asks the participant |
| `goal` | string | yes | what this question is for; researcher's intent statement |
| `must_get` | list[string] | yes | concrete signals the answer must contain to be considered sufficient |
| `max_followups` | int (1-5) | yes | hard cap on probes for this question |
| `probe_instruction` | string \| null | no | researcher-written guidance on how to probe; expanded at session start (see Req 8) |

**Req 3**: The system **shall** reject any outline with duplicate question `id` values, `max_followups` outside `[1, 5]`, or empty `ask`/`goal` fields. Validation happens in the API layer; engine assumes valid input.

**Req 4**: Sections **shall** preserve the order researchers wrote. The engine traverses sections in array order, questions in array order. There is no skip, no jump, no conditional branch (a future ADR may reintroduce this; v3 explicitly does not).

---

## 3. Follow-up mode (Req 5–9)

**Req 5**: Each `InterviewSession` **shall** have one immutable `follow_up_mode` value, set at session start by the participant or moderator:

| Value | Meaning | LLM calls per turn (judge step) |
|---|---|---|
| `"off"` | no probing, advance immediately after each reply | 0 |
| `"standard"` | probe when answer obviously misses must_get items; lenient bar | 1 |
| `"deep"` | probe until each must_get item has concrete evidence; strict bar; budget × 2 | 1 |

**Req 6**: The system **shall** persist `follow_up_mode` on `InterviewSession`. Migration adds the column with default `"standard"` for existing rows.

**Req 7**: When `follow_up_mode = "off"`, the engine **shall not** call any LLM between user reply and next-question advance. The judge_off node is structurally present but does no LLM work.

**Req 8**: At session start (before the first question is asked), the engine **shall** make at most one LLM call to expand each question's `probe_instruction` (when present) into actionable probing strategy notes. Expansion result is stored in graph state under `probe_strategies: dict[qid, str]` and **shall not** be regenerated on resume or per turn.

   - 8.1: When all questions have `probe_instruction = null`, the expansion step **shall** skip the LLM call and store an empty dict.
   - 8.2: The expansion **shall not** modify `ask`, `goal`, or `must_get`; only `probe_instruction` is rewritten.
   - 8.3: The expansion result **shall** be available to `judge_standard` and `judge_deep` when generating the next probe question.

**Req 9**: Per-turn LLM call budget **shall** stay at most 2 (extract+probe pattern, AGENTS.md Rule 4 preserved):
   - judge_off mode: 0 calls per turn
   - judge_standard / judge_deep mode: 1 judge call (returns sufficient + optional probe text)

   The probe text is part of the judge call's structured output, not a separate "generate" call. v3 collapses v1's two-call pattern into one when probing is needed.

---

## 4. Engine behavior (Req 10–14)

**Req 10**: Engine **shall** present the current question via `interrupt({"question": ask, "kind": "main"})`. The runner unblocks when `Command(resume=user_text)` arrives.

**Req 11**: When `judge.sufficient = true` OR `probe_count >= effective_max_followups`, the engine **shall** advance to the next question. `effective_max_followups` is `max_followups` for `standard` mode and `max_followups * 2` for `deep` mode.

**Req 12**: When `judge.sufficient = false` AND `probe_count < effective_max_followups`, the engine **shall** emit a probe via `interrupt({"question": probe_text, "kind": "followup"})` and increment `probe_count`.

**Req 13**: After the last question of the last section, the engine **shall** invoke `finish_interview` once: one LLM call summarizes the transcript, output stored as `final_report` in graph state.

**Req 14**: The engine **shall not** rewrite, paraphrase, or substitute any question's `ask` field. The string the researcher wrote is the string spoken to the participant, verbatim.

---

## 5. Persistence (Req 15–18)

**Req 15**: Mid-session graph state **shall** persist via LangGraph's `PostgresSaver` (or `AsyncPostgresSaver`) checkpointer. The thread id **shall** equal `str(InterviewSession.id)`.

**Req 16**: Checkpoint storage **shall** use a dedicated table (e.g. `merism_lg_checkpoint`), separate from `merism_session_event`. v3 does not write per-turn `SessionEvent` rows. Rule 9 (event sourcing as runtime authority) is **relaxed for v3**: ADR 0012 documents the relaxation; analytics consumes the final transcript instead of replaying events.

**Req 17**: At `finish_interview` completion, the engine **shall** write the full transcript (list of turns) to `InterviewSession.transcript` (existing `JSONField`). One row per session, atomic write. Existing analytics / report code reads this field unchanged.

**Req 18**: Resuming a partially-completed interview **shall** continue from the last checkpoint. Calling `graph.invoke(Command(resume=text), thread_id=session_id)` for a session whose graph is not at an `interrupt()` **shall** return immediately with the current state without erroring.

---

## 6. Routing & coexistence (Req 19–21)

**Req 19**: A new helper `merism.conductor_v3.router.is_v3_session(session)` **shall** return true when `session.guide and session.guide.sections.get("version") == "v3"`.

**Req 20**: `merism.api.interview_message_view.stream_messages` and `merism.realtime.voice.VoiceConsumer.connect` **shall** route v3 sessions to v3, and all other sessions to v1 `stream_turn`. v2 routing is removed (v2 is deleted).

**Req 21**: New studies created via the wizard **shall** default to v3 outline shape (`{"version": "v3", "sections": []}`). Existing v1 studies remain on v1 indefinitely; there is no automatic migration command (v1 retirement, if ever, is a future ADR).

---

## 7. Voice integration (Req 22–24)

**Req 22**: A pipecat `FrameProcessor` (`merism.voice.processors.moderator_v3.ModeratorV3Processor`) **shall** wrap the v3 graph for voice sessions. The processor:
   - On `TranscriptionFrame`: invokes `graph.invoke(Command(resume=text))`, extracts the next interrupt payload, pushes its `question` text as `LLMTextFrame` (start/text/end trio).
   - On 60s idle (timer owned by processor, not by the graph): synthesizes empty resume, lets the graph re-judge.
   - On `EndFrame` / `CancelFrame`: cancels in-flight LLM calls, lets checkpointer persist current state.

**Req 23**: The voice pipeline for v3 sessions **shall** be `[STTProcessor, ModeratorV3Processor, TTSProcessor, ConversationState]`. The `UserIdleDetector` is omitted (the processor owns idle handling).

**Req 24**: Barge-in handling **shall** stay in pipecat's frame layer. The graph receives only `Command(resume=...)` calls, not raw audio events.

---

## 8. Failure handling (Req 25–28)

**Req 25**: Any LLM call inside a node **shall** wrap the call in `try/except`. On failure:
   - `prepare_session` failure: log, store empty `probe_strategies`, continue (Req 8.1 fallback).
   - `judge_standard` / `judge_deep` failure: log, return `{"sufficient": True, "missing": [], "followup": None, "reason": "judge_unavailable"}` so the engine advances rather than hangs.
   - `finish_interview` failure: log, store an error placeholder in `final_report`, mark session complete anyway.

**Req 26**: The engine **shall not** raise exceptions out of node functions. Any unrecoverable condition is logged via `logger.exception(...)` and converted to a state field (e.g. `last_error: str | None`).

**Req 27**: When `interrupt()` is hit and the runner returns the payload to caller, the caller (HTTP view or voice processor) **shall** be responsible for ensuring the next `Command(resume=...)` arrives. The graph does not time out on its own; voice processor's 60s idle counts as the de-facto timeout.

**Req 28**: Frontend **shall** show a clear error state when the v3 engine reports `last_error != null` and let the participant retry the current question.

---

## 9. Test coverage (Req 29–32)

**Req 29**: Unit tests **shall** cover each node in isolation with mocked LLM:
   - `prepare_session`: with/without `probe_instruction` per question; LLM failure path
   - `ask_and_wait`: interrupt payload shape; resume cycle
   - `judge_off`: never calls LLM; always sufficient=True
   - `judge_standard` / `judge_deep`: budget tracking; pending_followup propagation; LLM failure → advance
   - `advance_cursor`: section/question cursor progression; done flag at end
   - `finish_interview`: transcript formatting; LLM failure path

**Req 30**: Integration tests **shall** cover full outline traversal end-to-end with a recording mock LLM, in each of the three modes.

**Req 31**: Live LLM tests (`@pytest.mark.merism_llm_live`) **shall** run a 5-question outline against DeepSeek in `standard` mode. Acceptance: ≥ 4/5 sessions complete without LLM exceptions; final report non-empty; transcript length within ±20% of expected (8-15 turns).

**Req 32**: Voice processor unit tests **shall** verify frame routing, bootstrap idempotency, and EndFrame teardown without an actual audio pipeline.

---

## 10. Out of scope (explicitly rejected for v3)

- Typed slot schema (`SlotSchema` with type/enum_values/description fields)
- `skip_if` cross-question jumps (researcher-defined branching)
- Behavior slot taxonomy (refused / evasive / off_topic / pre_answered / garbled)
- Per-turn `SessionEvent` event sourcing as runtime authority
- Visual graph editor for researchers (researchers write list of questions)
- Multi-agent orchestration (single graph, single thread per session)
- AI-driven edge decisions (all transitions are pure routing functions over typed state)
- Question text rewriting at session start (only `probe_instruction` is rewritten; questions are verbatim)

If you want any of these back, write a new ADR and amend this spec. Do not smuggle them in via PR.

---

## References

- ADR 0012 — decision to adopt LangGraph for v3 (writes itself last, after this spec is approved)
- AGENTS.md Rule 4 (2 LLM calls per turn — preserved by collapsing extract+generate into one judge call)
- AGENTS.md Rule 9 (event sourcing — relaxed for v3, ADR 0012 documents the trade)
- AGENTS.md Rule 12 (AI is content-only — preserved; transitions are pure routing)
- AGENTS.md Rule 13 (dual-engine routing — extended to v3 via `version: "v3"` literal)
