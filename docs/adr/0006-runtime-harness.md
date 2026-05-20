# ADR 0006 — Minimal runtime harness (no Temporal, no LangGraph, no OpenHands controller)

Date: 2026-05-11
Status: accepted
Supersedes: —

## Context

End-to-end automation was needed for the invite → interview → insight →
inbox chain. Before this change:

- `moderator.stream_turn` was implemented but had **zero callers** —
  voice pipeline ran a generic `LLMProcessor` with a hardcoded system
  prompt, ignoring `study.guide`.
- Sessions never auto-transitioned to COMPLETED.
- `post_session` pipeline had a signal handler but nothing triggered
  it because #2 above.
- No cross-module correlation — logs for one participant were
  scattered without any way to stitch the journey back together.

The surface problem looked like "wire moderator to voice". The deeper
problem was the lack of a **runtime contract** between all the
cross-module signals (WS events, Celery tasks, admin actions, HTTP
views) that share a session's lifetime.

## Options considered

### Option A — Temporal / Restate (durable workflow runtime)

+ Long-running workflows with persistence built in.
+ State survives process restart without ceremony.
- Separate service to run + monitor.
- Team unfamiliar with it; learning curve non-trivial.
- Overbuilt for 45-minute max session.

### Option B — LangGraph (graph-based agent state machine)

+ Ecosystem fit for LLM agents.
+ Checkpointing + resume out of the box.
- PRODUCT.md §5.2 explicitly forbids multi-node graphs for the
  moderator (the 2-node decide → generate pipeline lives inside one
  ``stream_turn`` coroutine; no graph framework needed).
- Adds a mental model competing with Django's ORM + signal model.

### Option C — OpenHands-style `AgentController` + `EventStream` + `Runtime`

+ Clean event sourcing pattern worth emulating.
+ Runtime abstraction for tool execution.
- Merism moderator has a **fixed 4-action enum** (no tool selection).
  The entire `Runtime` layer is unused.
- Agent controller adds complexity with no corresponding benefit.

### Option D (chosen) — Event log + trace_id + signals

+ Steal the good idea (event sourcing as authoritative log) without
  the orchestration baggage.
+ Postgres append-only rows give the same semantics as Kafka /
  EventStore for our scale.
+ Django signals + Celery + structlog already in the stack.
+ Easy to keep in-head: one table, two service functions, one context
  manager.

## Decision

1. `merism_session_event` is the **authoritative record** of what
   happened in an interview. `InterviewSession.{moderator_state,
   transcript, decision_log}` become **derived caches**, rebuildable
   via `reconstruct_state()`. This gives us resumability without any
   durable-workflow runtime.

2. Every row on `Invitation / DeliveryRecord / Participation /
   InterviewSession / SessionEvent / SessionInsight / InboxItem`
   carries a `trace_id: UUIDField`. One UUID ties a participant's
   journey across seven tables + all structlog output inside
   `bind_trace(...)` blocks.

3. Six closure signals OR'd together decide when a session ends. The
   LLM's `close` decision is one signal of six — rules (max duration,
   idle timeout, leaving intent, WS disconnect) can fire
   independently. This prevents the LLM's helpful-always training from
   running sessions forever.

4. `Study.actual_completed_count` is a `@property` that runs
   `COUNT(*)`, not a stored counter. Race-free by construction.

5. `process_completed_session` launches a Celery `chain` of three
   stage tasks (`polish → extract_and_tag → index_and_insight`). Each
   stage retries independently; any one failure doesn't re-run earlier
   successful stages.

No new infrastructure. No new service. No new language. The whole
harness is ~800 lines of Python + 5 migrations.

## Consequences

- **Good**: Any worker can read a session's events and reconstruct
  state. Process restart mid-session is safe.
- **Good**: Admin `Trail` view and structlog queries both use
  `trace_id` — one grep to follow a participant end-to-end.
- **Good**: No extra ops burden. No new dashboard to learn.
- **Neutral**: `moderator_state` / `decision_log` are caches —
  contributors must remember not to treat them as authoritative.
  Codified as rule 9 in AGENTS.md.
- **Risky (acknowledged)**: At higher scale, querying
  `SessionEvent` for state reconstruction on every moderator turn
  could become slow. Today's sessions have < 100 events each, so the
  query is O(1) with the `(session, seq)` index. If a future product
  (e.g. multi-day async interviews) pushes this up, migrate to a
  compact snapshot every N events (not before).

## References

- `docs/RUNTIME.md` — full design writeup
- `merism/conductor/README.md` — module docs
- `merism/tests/test_e2e_automation.py` — end-to-end test
