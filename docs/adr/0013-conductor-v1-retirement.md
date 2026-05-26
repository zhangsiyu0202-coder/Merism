# ADR 0013 — Conductor v1 retirement

Date: 2026-05-23
Status: accepted
Supersedes: nothing (v1 was retired by deletion, no prior ADR formalised it)
Related: ADR 0012 (v3 LangGraph), ADR 0009 (v2 list interpreter — superseded), ADR 0007/0008 (earlier v2 attempts — superseded)

## Context

Conductor v1 (`merism.conductor.moderator.stream_turn`) was the 2-node
decide → generate moderator that shipped in R23 (2026-05-18). v3
(LangGraph, ADR 0012) shipped 2026-05-23 and proved itself across:

- 142 unit tests + 2 voice integration tests passing
- 1 live-LLM smoke (5-question outline, 100% well-formed responses)
- 3 rounds of stress testing (9-question outline × 3, perfect determinism)
- 1 real DashScope STT + TTS end-to-end roundtrip
- Verified `post_session` pipeline compatibility on v3 transcript shape

By 2026-05-23 every active study (23 InterviewGuides) had been
migrated to v3 schema via `migrate_guide_to_v3`. Continuing to maintain
the v1 code path was net-negative: dual-engine routing + v1 voice
processor + v1 prompts (~5000 LOC) sit unused but still compiled,
tested, and reasoned about by every contributor.

## Decision

Delete v1. Single-engine v3.

### Removed code

`merism/conductor/`:
- `moderator.py` — 2-node engine
- `decision_prompt.py` / `decision_validator.py` / `generation_prompt.py` — v1 prompts
- `guide_cursor.py` — v1 cursor traversal
- `probe_blocks.py` / `adaptive_probing.py` — v1 probing logic
- `concept_plan.py` — v1 concept-testing scoping
- `state.py` — v1 `ExecutionState`
- `prompts.py` — v1 system prompt builder
- `moderator_eval.py` — v1 evaluator harness
- `event_log.py` — v1 SessionEvent emitters
- `closure.py` — v1 6-signal closure
- `text_chunker.py` — v1 TTS chunker
- `tests/test_*.py` — v1 unit tests (kept: `test_llm_polish.py`, `test_transcript_helpers.py`)

`merism/voice/`:
- `processors/moderator.py` — v1 voice LLM processor
- `interview_pipeline.py` — v1 voice pipeline orchestration
- `services/moderator_processor.py` — v1 voice service helper
- `tests/test_moderator_*.py` — v1 voice unit tests
- `realtime/tests/test_voice_consumer.py` — v1 voice consumer tests
- `realtime/tests/test_truncation_flow.py` — v1 truncation tests

`merism/management/commands/`:
- `evaluate_moderator.py` — v1 batch eval CLI
- `migrate_probe_blocks.py` — v1 → v1.1 probe block migration

Total deleted: ~5000 LOC + ~2000 LOC of v1 tests.

### Retained as cross-engine helpers

`merism/conductor/` keeps:
- `post_session.py` — orchestrates transcript polish + insight + report (used by both engines)
- `transcript_helpers.py` — used by `quote_extractor` and `post_session`
- `llm_polish.py` — transcript cleaning (used by `merism.cleaning.pipeline`)
- `rule_clean.py` — rule-based pre-clean (used by `llm_polish`)
- `signals.py` / `study_closure_signal.py` / `inbox_signals.py` — Django signal handlers
- `tasks.py` — Celery tasks for transcript polishing + post-session

`merism/conductor/__init__.py` is now a small façade module documenting
this; it does not re-export interview-engine entry points.

### Routing simplified

- `merism/api/interview_message_view.py` — drops the `is_v3_session` branch; all sessions go through `run_v3_turn`.
- `merism/realtime/voice.py` — drops the `is_v3` dispatch; sessions with `guide_id` use `ModeratorV3Processor`, sessions without (ad-hoc chat) keep the generic `LLMProcessor`.
- `merism/conductor_v3/router.py` — `is_v3_session` predicate retained for defensive reads of legacy data, but no longer used by the request path.

### AGENTS.md updates

- **Rule 4** rewritten: single-engine v3, ≤1 LLM call/turn (judge), 0/session outside the turn loop.
- **Rule 9** retains the v3 exception clause from ADR 0012 — LangGraph checkpoint is the runtime authority, transcript writes once at session end.
- **Rule 12** unchanged — AI is content-only, routing is pure functions.
- **Rule 13** rewritten: single-engine v3, no dual-engine routing, no cross-engine import concern.

### Data migration

`migrate_guide_to_v3 --all-studies --apply` was run 2026-05-23, before
the deletion. 23/23 active v1 guides migrated cleanly. v1 list-shape
guides no longer exist in production data.

Field mapping locked in the migration command:
- v1 `text` → v3 `ask`
- v1 `probe_policy` (none/light/standard/deep) → v3 `follow_up_mode` (off/standard/standard/deep)
- v1 `probe_directions` → v3 `probe_instruction` (joined when list)
- v1 `followup_depth` / `max_probes` / `required` / `intent` / `linked_stimulus_ids` / `type` / `scope` / `concept_block_id` → DROPPED

## Consequences

### Positive

- Single engine to reason about. New contributors don't need to learn the v1 2-node pattern.
- ~5000 LOC engine + ~2000 LOC tests deleted. Faster CI, smaller import surface.
- Cross-engine import boundary removed — no more "is this allowed in v1 or v3?" code review questions.
- `Outline.model_validate` strictly enforces v3 shape — ill-formed payloads fail fast at the API edge.

### Negative

- 38 historical completed sessions still reference the v1 `guide_snapshot` shape on `InterviewSession.guide_snapshot` and the v1 transcript shape on `InterviewSession.transcript`. Read-side code (analytics, reports) must be tolerant of both shapes — already true since v3 finalize writes v1-compatible transcript shape (per ADR 0012) and guide_snapshot is read-only history.
- `test_full_chain_invite_to_inbox` is skipped pending a v3 rewrite. The test asserted v1 `SessionEvent.kind` invariants that don't apply to v3. R29 will produce a v3-shaped equivalent.
- Two pre-existing baseline test failures (`test_stt_processor_commits_turn_on_explicit_stop`, `test_django_settings_is_merism_test`) remain — these were failing before v1 retirement and are not regressions.

### Neutral

- ROADMAP R29 entry documents v1 retirement.
- Frontend `outlineEditorLogic.ts` retains v1 schema for legacy UI rendering (the editor's own internal data model is unrelated to wire shape — it serializes to v3 on save). A future R30 will simplify the frontend editor too.

## Reversibility

Reversing this requires git revert + re-running migrations. The
`pre-v1-removal-2026-05-23` git tag captures the state before
deletion. Old v1 guide payloads are not recoverable from production —
the migration was destructive (overwrote `InterviewGuide.sections`),
so reverting code without revert+restore of guide rows would leave
the system inconsistent.

In practice we do not plan to revert. v3 has been validated end-to-end
in text mode (real DeepSeek), voice mode (real DashScope STT + TTS),
and post-session pipeline integration.

## References

- ADR 0012 — v3 LangGraph adoption
- `docs/specs/conductor-v3/` — v3 spec
- `merism/management/commands/migrate_guide_to_v3.py` — migration command
- Git tag `pre-v1-removal-2026-05-23` — pre-deletion snapshot
- AGENTS.md Rules 4, 9, 12, 13
