# Conductor v3 — Implementation Plan

> Implements `requirements.md` per `design.md`. Each task ends with: `pytest merism/conductor_v3/tests` + `ruff check . --fix && ruff format .` + `pyright merism` + (frontend tasks) `pnpm --filter merism-frontend typecheck`.

> **Pattern contract**: every PR in this plan **shall** comply with `design.md` §0 (Pattern provenance) — file split, state decomposition, `Annotated[list, operator.add]` reducer, `Configuration.from_runnable_config()`, node signature `(state, config: RunnableConfig) -> dict`, prompts in `prompts.py`, structured output via `with_structured_output(method="json_mode")`. Code review rejects violations. ADR 0012 binds these as architectural contract.

---

## Phase 1 — schema + state + configuration (1 day)

### P1.1 — `merism/conductor_v3/schema.py`

- `Question / Section / Outline` Pydantic models; `extra="forbid"`; `id` regex `^[a-zA-Z0-9_]+$`.
- `Turn` TypedDict.
- `validate_outline(outline) -> None` raising `OutlineError`; `flatten_questions(outline)` returning `[(Section, Question)]` in traversal order.
- Tests: `tests/test_schema.py` covers field validation (max_followups bounds, empty ask/goal rejection), duplicate-id rejection, flatten ordering.

### P1.2 — `merism/conductor_v3/state.py`

- `OverallState / JudgeOutput / AdvanceOutput` TypedDicts.
- `transcript: Annotated[list[Turn], operator.add]` reducer.
- Tests: `tests/test_state.py` verifies that calling LangGraph with `{"transcript": [t1]}` then `{"transcript": [t2]}` accumulates rather than overwrites.

### P1.3 — `merism/conductor_v3/configuration.py`

- `Configuration(BaseModel)` per design § 6.
- `from_runnable_config()` classmethod loading from env vars (uppercased) + `RunnableConfig.configurable` overrides.
- Tests: `tests/test_configuration.py` covers default values, env override, configurable override priority.

---

## Phase 2 — LLM contract (1 day)

### P2.1 — `merism/conductor_v3/tools_and_schemas.py`

- `Evaluation` Pydantic with `sufficient / missing / followup / reason`.
- `ProbeStrategies` Pydantic with `strategies: dict[str, str]`.
- Tests: `tests/test_tools_and_schemas.py` covers field defaults + extra=forbid behavior.

### P2.2 — `merism/conductor_v3/prompts.py`

- 4 module-level templates: `PROBE_EXPAND_PROMPT / JUDGE_STANDARD_PROMPT / JUDGE_DEEP_PROMPT / FINALIZE_PROMPT`.
- Each template ends with `返回 JSON: {...}` so DeepSeek json_mode passes its safety check.
- Tests: `tests/test_prompts.py` verifies each template contains the literal `JSON` and accepts the expected `.format(...)` keys.

### P2.3 — `merism/conductor_v3/llm.py`

- `build_llm(model, *, temperature)` returns `ChatOpenAI` configured for DeepSeek.
- `build_evaluator(llm, schema)` returns `llm.with_structured_output(schema, method="json_mode")`.
- Tests: `tests/test_llm.py` mocks `ChatOpenAI` and asserts `method="json_mode"` is passed.

---

## Phase 3 — nodes (2 days)

### P3.1 — `prepare_session` node

- Skips LLM call when no question has `probe_instruction`.
- Otherwise: 1 LLM call returning `ProbeStrategies`.
- LLM failure → empty `probe_strategies` (Req 25).
- Tests: `tests/test_nodes_prepare.py`
  - 4 cases: no probe_instruction (no LLM call), one probe_instruction, all probe_instruction, LLM exception.

### P3.2 — `ask_and_wait` node

- Reads cursor; picks `pending_probe` or `qspec.ask`; calls `interrupt(payload)`.
- Resume returns user text; appends single `Turn` to `transcript`.
- Tests: `tests/test_nodes_ask.py`
  - main question vs pending probe; transcript reducer accumulates.

### P3.3 — `judge_off` node

- Returns `{pending_probe: None, last_evaluation: {sufficient: True, skipped: True}}`. Asserts no LLM is called (mock raises if invoked).

### P3.4 — `judge_standard` and `judge_deep` nodes

- Implementation via shared `_judge_with_prompt(state, config, template, multiplier)` helper.
- `_format_transcript_tail(state, n)` helper.
- LLM failure → advance with `last_error` set.
- Tests: `tests/test_nodes_judge_standard.py`, `tests/test_nodes_judge_deep.py`
  - LLM returns sufficient=True → pending_probe None.
  - LLM returns sufficient=False with followup → pending_probe set, count++.
  - probe_count >= effective_max → advance even if sufficient=False.
  - deep mode applies `multiplier`.
  - LLM exception → advance + last_error.

### P3.5 — `advance_cursor` node

- Within section: `question_i++`. Section boundary: `section_i++`, `question_i=0`. End: `done=True`.
- Tests: `tests/test_nodes_advance.py`
  - 3 cases: mid-section, section boundary, end of outline.

### P3.6 — `finish_interview` node

- 1 LLM call producing `final_report` markdown.
- LLM failure → fallback report containing raw transcript + error marker.
- Tests: `tests/test_nodes_finish.py`
  - happy path; LLM exception → fallback contains transcript.

---

## Phase 4 — graph + checkpointer (1 day)

### P4.1 — `merism/conductor_v3/graph.py`

- Build `StateGraph(OverallState, config_schema=Configuration)`.
- Wire 7 nodes per design § 9 diagram.
- 3 routing functions: `route_after_ask / route_after_judge / route_after_advance`.
- `compile(checkpointer=PostgresSaver.from_conn_string(LG_CHECKPOINT_DB_URL))`.

### P4.2 — Checkpoint setup migration

- Create `merism/migrations/0038_langgraph_checkpoint_setup.py` running `PostgresSaver.setup(conn)` to create LangGraph's checkpoint tables.
- Add `MERISM_LG_CHECKPOINT_DB_URL` to `merism/settings/base.py` (defaults to same DB as Django, separate schema).

### P4.3 — Routing tests

- `tests/test_graph_off_mode.py`: full traversal, mode=off, no LLM calls between turns.
- `tests/test_graph_standard_mode.py`: full traversal, mode=standard, with mock judge returning sufficient=True after first probe.
- `tests/test_graph_deep_mode.py`: full traversal, mode=deep, verify `effective_max = max_followups * multiplier`.
- `tests/test_graph_resume.py`: invoke until interrupt, save state, fresh resume, verify byte-identical state continuation.

---

## Phase 5 — runner + persistence + router (1 day)

### P5.1 — `merism/conductor_v3/runner.py`

- `start_interview / answer_interview / get_interrupt_payload`.
- `graph_config(thread_id, configurable)` builder.

### P5.2 — `merism/conductor_v3/persistence.py`

- `finalize_to_session(session_id)` — async; reads graph state, writes `InterviewSession.transcript` + `moderator_state.final_report` + `status="completed"`.
- Idempotent: re-calling on already-completed session is no-op.
- Tests: `tests/test_persistence.py`
  - Happy path: completed graph → InterviewSession updated.
  - Incomplete graph: no write.
  - Idempotency: 2nd call is no-op.

### P5.3 — `merism/conductor_v3/router.py`

- `is_v3_session(session) -> bool` per design § 12.
- Tests: `tests/test_router.py`
  - 4 cases: v3 dict, v1 list, no guide, dict without version.

### P5.4 — `merism/models/migrations/...`

- Migration adding `InterviewSession.follow_up_mode VARCHAR(16) NOT NULL DEFAULT 'standard'`.
- Update `InterviewSession` model field with `choices=[("off",...),("standard",...),("deep",...)]`.

---

## Phase 6 — tests roundup (0.5 day)

### P6.1 — `tests/fakes.py`

- `FakeLLM(responses: list[BaseModel])` — `invoke()` pops from list; raises if empty.
- `RecordingChannel(answers: list[str])` — for `interrupt()` simulation.

### P6.2 — `tests/fixtures/sample_outlines.py`

- `OUTLINE_3Q_BASIC` — minimal 3-question outline, no probe_instruction.
- `OUTLINE_5Q_LIVE` — 5-question outline with probe_instruction on every question, used by live LLM smoke.

### P6.3 — `tests/test_live_smoke.py`

- `@pytest.mark.merism_llm_live + merism_slow`.
- Run `OUTLINE_5Q_LIVE` in `standard` mode against DeepSeek.
- Acceptance: 4/5 reps complete without exception; final_report non-empty; transcript length 8-15 turns.

### P6.4 — Verify

- `pytest merism/conductor_v3/tests` — all green (live smoke skipped without API key).
- `ruff check merism/conductor_v3` + `ruff format --check merism/conductor_v3` — green.
- `pyright merism/conductor_v3` — 0 errors.

---

## Phase 7 — API + voice integration (1.5 days)

### P7.1 — Text mode wiring

- `merism/api/interview_message_view.py` — when `is_v3_session(session)`, route to a new `run_v3_text_session(session, message)` async generator that wraps `answer_interview` and yields token chunks (or whole response, depending on streaming UX).
- Tests: `merism/api/tests/test_interview_message_view_v3.py`
  - 3 cases: v3 session → v3 path; v1 session → v1 path; missing guide → v1 path.

### P7.2 — Outline API

- `merism/api/views.py` — replace the 501 stub of `outline_action` with v3 GET / PUT:
  - GET returns Outline JSON or empty default `{"version": "v3", "sections": []}`.
  - PUT validates via Pydantic + `validate_outline`; 422 with `{"outline_errors": [...]}` on failure; persists as new `InterviewGuide` row with `is_current=True` flip.
- Tests: `tests/test_outline_action_v3.py`
  - GET empty study; PUT valid; PUT invalid (duplicate id); PUT invalid (missing fields); cross-team 404.

### P7.3 — Voice processor

- `merism/voice/processors/moderator_v3.py` per design § 13.
- Tests: `merism/voice/tests/test_moderator_v3_processor.py`
  - Bootstrap on StartFrame; submit on TranscriptionFrame; idle timer cancel/restart; EndFrame teardown.

### P7.4 — Voice routing

- `merism/realtime/voice.py` — when `is_v3_session(session)`, build pipeline `[STTProcessor, ModeratorV3Processor, TTSProcessor, ConversationState]`. Otherwise existing v1.
- Tests: `merism/realtime/tests/test_voice_routing.py` (or extend existing).

---

## Phase 8 — frontend + ADR + cleanup (1 day)

### P8.1 — Frontend OutlineTab

- `frontend/src/features/studies/tabs/outline/types.ts` — add `V3Question` type with 5 required fields + `probe_instruction?`.
- `outlineEditorLogic.ts` — add `follow_up_mode` action + reducer; expose 3-radio control.
- `OutlineTab.tsx` — render V3 questions: collapsible card per question with `id / ask / goal / must_get (chip list editor) / max_followups (number input) / probe_instruction (textarea)`.
- Top of OutlineTab: 3-state radio for `follow_up_mode` (off / standard / deep).
- Tests: pnpm typecheck + pnpm lint + manual visual check.

### P8.2 — ADR 0012

- Write `docs/adr/0012-conductor-v3-langgraph.md`.
- Status: accepted.
- Supersedes: ADR 0009 (list interpreter) and ADR 0011 (framework evaluation deferred).
- Documents: AGENTS.md Rule 9 relaxation; Rule 4 reframing (per-turn ≤ 2 LLM calls; finalize is per-session); 3-mode follow-up.

### P8.3 — AGENTS.md updates

- Rule 4: rephrase to "v3: at most 1 LLM call between user turns; finalize is a per-session call. v1 keeps its 2-call (decide+generate) shape."
- Rule 9: add v3 exception clause — graph state via LangGraph checkpoint; final transcript at `InterviewSession.transcript`; per-turn `SessionEvent` not authoritative for v3.
- Rule 13: routing key updated to `version: "v3"` for v3; `version: "v2"` is a removed schema (any session still carrying it is invalid).
- Drop the "Engine architecture (R26+ Conductor v2)" section; replace with a tighter "Engine architecture (v3)" pointer to `docs/specs/conductor-v3/`.

### P8.4 — ROADMAP

- Update `docs/ROADMAP.md` R28 entry: "Conductor v3 LangGraph rewrite — 4-mode topology with optional probe expansion. Replaces deleted v2."

---

## Phase 9 — Cross-suite regression (0.5 day)

- `pytest merism/conductor_v3/tests merism/voice/tests/test_moderator_v3_processor.py merism/api/tests merism/tests --tb=line -q`.
- Expected: ≤ 2 pre-existing failures (`test_full_chain_invite_to_inbox` + `test_django_settings_is_merism_test`); everything else green.
- `ruff check merism/conductor_v3 merism/voice/processors/moderator_v3.py merism/api/views.py merism/api/interview_message_view.py merism/realtime/voice.py` — green.
- `ruff format --check ...` — green.
- `pyright merism/conductor_v3` — 0 errors (Django ORM-coupled files keep baseline).
- `pnpm typecheck` — passed.
- `pnpm lint` — 0 errors.

---

## Total estimate

| Phase | Time |
|---|---|
| 1 — schema + state + config | 1 day |
| 2 — LLM contract | 1 day |
| 3 — nodes (7 nodes + 1 helper) | 2 days |
| 4 — graph + checkpointer | 1 day |
| 5 — runner + persistence + router | 1 day |
| 6 — tests roundup | 0.5 day |
| 7 — API + voice integration | 1.5 days |
| 8 — frontend + ADR + cleanup | 1 day |
| 9 — cross-suite regression | 0.5 day |
| **Total** | **~9.5 days (~2 weeks calendar)** |

Critical path: Phase 1 → 2 → 3 → 4. Phases 5-8 can interleave once graph compiles green.

---

## Out of scope for this implementation cycle

- Frontend `follow_up_mode` UX polish beyond a 3-state radio (visual treatment / icon / help text — punt to a future product pass).
- Per-team Configuration overrides via admin UI (env-var override is enough for v3 cutover; admin UI is a separate ticket).
- Replaying old v1 sessions through v3 (no migration, v1 stays on v1 until retired).
- Voice + v3 dogfood with real participants (P3.5 equivalent — gated on internal scheduling).
- A graph visualization in the frontend (LangGraph mermaid export is enough for engineer-side debugging).
