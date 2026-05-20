# `merism.conductor`

Interview runtime. **Two-node moderator pipeline** per participant turn:
non-streaming `coverage_steer` (decide) → streaming `generate` (speak),
both awaited in order inside the same `stream_turn` coroutine. No
macro/meso/micro split, no persistent policies — see PRODUCT.md §5.2
and `merism-platform` Req 14. The moderator **does not choose tools**;
its action space is a fixed enum (`followup / move_on / clarify /
close`). This constraint is what lets us skip the OpenHands-style
AgentController layer.

## Files

| File | Role |
|---|---|
| `state.py` | `ExecutionState` Pydantic model — rebuildable view over the event log |
| `prompts.py` | `ModeratorDecision` function-call schema + concept context formatter |
| `decision_prompt.py` | System prompt builder for Node 1 (coverage_steer) |
| `decision_validator.py` | Hard-cap validation (max_probes, probe_policy=none, dynamic-probe rules) — rejects illegal decisions without re-calling LLM |
| `generation_prompt.py` | System prompt builder for Node 2 (generate) |
| `probe_blocks.py` | Dynamic probe block schema + prompt formatting |
| `adaptive_probing.py` | `build_coverage_context` — pulls fresh CoverageSnapshot for the decision prompt |
| `text_chunker.py` | TTS-friendly sentence chunker on streamed deltas |
| `moderator.py` | `stream_turn(session, participant_message)` — orchestrates Node 1 → validator → Node 2; persists events + state inline |
| `moderator_eval.py` | Offline eval harness (replays canned turns against either single-call legacy or 2-call current variant) |
| `guide_cursor.py` | `find_question` / `next_question` / `followup_budget` / `dynamic_probe_config` — pure guide traversal |
| `event_log.py` | `append_event` / `reconstruct_state` / `current_transcript` — atomic writes to `SessionEvent`; authoritative record |
| `closure.py` | 6-signal OR closure + `complete_session` + `abandon_stuck_sessions` orphan cleanup |
| `concept_plan.py` | Concept Testing 2.0 — expand per_concept sections, transition payloads |
| `post_session.py` | Async orchestrator (polish → codebook → quotes → tags → index → insight) |
| `llm_polish.py` | Batched LLM polish for transcript turns (delegated by `merism.cleaning`) |
| `rule_clean.py` | Filler-word regex cleanup (delegated by `merism.cleaning`) |
| `transcript_helpers.py` | Read-only transcript projections (`get_transcript_text`, `has_clean_transcript`) |
| `tasks.py` | Celery shims — `process_completed_session` launches a 3-stage chain |
| `signals.py` | `post_save(InterviewSession)` → enqueue post-session chain when COMPLETED |
| `study_closure_signal.py` | `post_save(Participation)` → auto-close Study when target reached |
| `inbox_signals.py` | `post_save` handlers writing `InboxItem` for session/insight/study completion |

## Runtime model (one turn)

```
Participant turn → stream_turn(session, user_text)
  ├── ExecutionState.model_validate(session.moderator_state)  (cached view)
  ├── client.chat.completions.create(stream=True, tools=[...])
  │     ├── content chunks          → yield to caller (TTS / SSE)
  │     └── tool_call arguments     → ModeratorDecision JSON
  ├── validate_decision(decision, state)                      (probe_policy + max_probes hard cap)
  ├── _apply_decision_to_state(state, decision)
  ├── session.moderator_state = state.dump()                  (cache write)
  ├── append_events(session, [user_turn, model_reply, decision])   AUTHORITATIVE
  └── _acheck_closure(session)                                (6-signal OR)
        └── complete_session(...) if signal → status=COMPLETED
```

`SessionEvent` is append-only, monotone `seq` per session. Caches
(`moderator_state`, `decision_log`, `transcript`) can be rebuilt from
events at any time via `reconstruct_state()` — this is our resumability
contract. Tests cover replay correctness.

## Closure signals (OR logic, first match wins)

| Signal | Trigger |
|---|---|
| `close_decision` | Moderator emitted `next_action == "close"` |
| `all_p0_answered` | Every P0 `StudyGoal.is_answered` AND elapsed ≥ `min_duration_minutes` (default 5) |
| `leaving_intent` | Regex match on last user_turn text (`bye / 再见 / …`) |
| `idle_timeout` | No user_turn for > 120s |
| `ws_disconnect` | WS disconnected ≥ 30s AND turn_count ≥ 4 |
| `max_duration` | elapsed ≥ `max_duration_minutes` (default 45) |

Orphan cleanup: `abandon_stuck_sessions` runs every 10 minutes (Celery
beat) and moves in-progress sessions older than 2h to COMPLETED.

## Post-session Celery chain

```
process_completed_session.delay(session_id)
  └── chain(
        stage_polish_transcript.si(sid),
        stage_extract_and_tag.s(),
        stage_index_and_insight.s(),
      )
```

Each stage has independent retry (3 × 30s) + observability via Flower.
`process_completed_session_inline` kept as the synchronous path for
admin replay actions.

## Auto-close mechanics

`Study.actual_completed_count` is an **aggregate property**, not a
stored counter — no race-prone `+= 1`:

```python
@property
def actual_completed_count(self) -> int:
    return self.participations.filter(
        status="completed", is_preview=False
    ).count()
```

Admin / API N+1 avoidance: `Study.annotate_completed_count()`.

When a Participation saves with status=COMPLETED and the study hits
target, `study_closure_signal` flips `Study.status=CLOSED` and all
matching `StudyLink.is_active=False` atomically
(`select_for_update` on the Study row).

## Deliberately not here

- ❌ `macro.py` / `meso.py` / `micro.py` — three-layer split forbidden by spec
- ❌ `policies/` — YAGNI until 100+ real interviews show need
- ❌ LangGraph / Temporal — Celery + event log is enough for Merism's scale
- ❌ OpenHands `AgentController` — moderator's 4-action enum needs no tool space

## Tests

| File | Count | Focus |
|---|---|---|
| `tests/test_event_log.py` | 9 | Atomic seq allocation + replay correctness |
| `tests/test_moderator_events.py` | 2 | Per-turn event writes + max_probes hard cap |
| `tests/test_closure.py` | 7 | 6 signals + idempotence + orphan cleanup |
| `tests/test_decision_validator.py` | — | probe_policy / max_probes overrides |
| `tests/test_concept_plan.py` | — | Concept rotation expansion |
| `tests/test_llm_polish.py`, `test_rule_clean.py`, `test_transcript_helpers.py` | — | Supporting |
