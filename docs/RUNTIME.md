# Merism runtime architecture

This doc describes Merism's runtime: how a participant goes from
receiving an invite to having their interview analyzed and surfaced to
the researcher, entirely without human intervention.

The design is minimal-but-exhaustive: no Temporal, no LangGraph, no
OpenHands-style `AgentController`. The insight is that Merism's
moderator has a **fixed 4-action enum** (`followup / move_on /
clarify / close`) — it does not select tools — so the whole class of
"agent runtime" abstractions built to orchestrate tool-choice is
unnecessary. What we keep from those projects is the **event-sourcing
discipline** and the **trace-id correlation pattern**.

## Data model for the runtime

Five tables carry the runtime:

| Table | Role | Appended by |
|---|---|---|
| `merism_invitation` | Per-recipient token bound to a StudyLink | `recruitment.tasks._delivery_context` |
| `merism_delivery_record` | Outbound IM / email send outcome | `recruitment.tasks.dispatch_recruitment_delivery` |
| `merism_participation` | Person-scoped state machine (INVITED→COMPLETED) | `/i/<slug>/` views + moderator closure |
| `merism_interview_session` | One actual conversation | `/i/<slug>/start/` + voice/text pipelines |
| `merism_session_event` | Append-only log of turn-level facts | `merism.conductor.event_log.append_event(s)` |
| `merism_session_insight` | Narrative summary per session | `memai.agents.session_insight_generator` |
| `merism_inbox_item` | Researcher-facing notification | `inbox_signals` |

Every row on all seven tables carries a `trace_id` (UUID). All rows
for one participant's journey share one `trace_id`, so admin Trail
view, structlog, and any future OpenTelemetry exporter can join them
without ambiguity.

## End-to-end flow

```
┌── Django admin ──────────────────────────────────────────────┐
│  Researcher: Study + Guide + Screener + ChannelConfig +     │
│              MessageTemplate + RecruitmentBroadcast          │
└──────────────────────────────────────────────────────────────┘
            ↓ admin approves broadcast
┌── Celery beat: dispatch_pending_broadcasts (catch-up) ──────┐
│  Every 60s: re-enqueue APPROVED/SENDING broadcasts that     │
│  lost their .delay() in a crash                             │
└──────────────────────────────────────────────────────────────┘
            ↓ Celery worker picks up
┌── recruitment.tasks.dispatch_recruitment_delivery ──────────┐
│  For each recipient:                                         │
│   1. get_or_create Invitation(recipient_hash, token)        │
│   2. Render template with study_link=/i/<slug>/?t=<token>   │
│   3. adapter.send_message(...) → IM / email provider        │
│   4. DeliveryRecord.status = SENT                           │
│   5. Invitation.status = DELIVERED                          │
│  All rows share trace_id                                    │
└──────────────────────────────────────────────────────────────┘
            ↓ recipient clicks URL
┌── merism/participant/views.py ─ GET /i/:slug/?t=<token> ────┐
│  resolve_link(slug, is_preview=False):                      │
│    ├── link.is_active / expires / study.status checks       │
│    ├── auto-close aware: study_full vs link_closed          │
│   _resolve_invitation(token):                                │
│    ├── invitation_required / invitation_invalid / expired   │
│   _get_or_create_participation(invitation):                  │
│    ├── rehydrate via cookie OR invitation binding           │
│    ├── Participation.trace_id = invitation.trace_id         │
│    └── quota check                                          │
│  → JSON { next_step: "consent" | "screener" | "session" }   │
└──────────────────────────────────────────────────────────────┘
            ↓ consent / screener steps
┌── POST /i/:slug/start/ ─────────────────────────────────────┐
│  Creates InterviewSession(trace_id=participation.trace_id)  │
│  Returns session_id → frontend routes to /interview/<id>    │
└──────────────────────────────────────────────────────────────┘
```

### Turn loop (voice and text share this)

```
text: POST /api/sessions/:id/message/  → SSE delta + done
voice: WebSocket /ws/sessions/:id/voice → LLMTextFrames → TTS
       ModeratorLLMProcessor(session_id=...)  (replaces plain LLMProcessor
       whenever session.guide_id is set)
```

Both surfaces delegate to **one** function:

```python
async for delta in merism.conductor.moderator.stream_turn(
    session, participant_message=user_text
):
    # stream delta back to caller
```

`stream_turn` does exactly these things per turn:

1. Load `ExecutionState` from `session.moderator_state` (cached).
2. Call LLM once with function-calling schema → streams **content**
   AND parses one `ModeratorDecision` tool_call.
3. Run `validate_decision` — hard-cap the LLM via
   `max_probes` and `probe_policy=none`. Illegal decisions get
   rewritten without another LLM call.
4. Apply decision to state (`mark_answered` / `mark_followup_used` /
   phase flip).
5. Persist `moderator_state` + `decision_log` + transcript on the
   session row (these are caches).
6. Append 3 rows to `SessionEvent` (`user_turn`, `model_reply`,
   `decision`) — **this is the authoritative log**.
7. Run `check_completion` — if any of 6 signals fires,
   `complete_session` sets `session.status = COMPLETED`,
   `participation.status = COMPLETED`, and emits a
   `session_lifecycle=ended` event.

Resumability: if the process dies mid-session, a new worker can call
`reconstruct_state(session)` which replays the event log and returns
the same `ExecutionState`. `moderator_state` is treated as a hint, not
truth.

## Closure — 6-signal OR

| Signal | Trigger |
|---|---|
| `close_decision` | LLM's decision = `close` |
| `all_p0_answered` | Every P0 goal `is_answered` AND elapsed ≥ min_duration |
| `leaving_intent` | Regex on last user_turn matches goodbye phrases (en + zh) |
| `idle_timeout` | No user_turn for > 120s |
| `ws_disconnect` | WS disconnected ≥ 30s AND ≥ 4 turns (tyre-kickers filtered) |
| `max_duration` | elapsed ≥ max_duration_minutes (default 45) |

Plus a 7th out-of-band: Celery beat task `abandon_stuck_sessions`
every 10 minutes moves anything in-progress > 2h to COMPLETED with
reason `max_duration`. This is the safety net for sessions whose
participant's browser tab was closed mid-turn.

`complete_session` is atomic (`select_for_update` on the session row)
and idempotent — double-fires collapse into one transition.

## Post-session pipeline (Celery chain)

`session.status = COMPLETED` fires `conductor.signals`, which enqueues
`process_completed_session(session_id)`. That task builds a Celery
`chain`:

```python
chain(
    stage_polish_transcript.si(session_id),  # intelligent-verbatim cleanup
    stage_extract_and_tag.s(),               # codebook seed + quote extract + tag
    stage_index_and_insight.s(),             # RAG index + SessionInsight
)()
```

Each stage is its own task. Retries (3 × 30s) apply per-stage; a
failure in `stage_extract_and_tag` doesn't re-run `stage_polish`. All
stages are idempotent at the domain level — `has_clean_transcript`,
`update_or_create(session=...)`, etc.

The synchronous monolithic path `process_completed_session_inline` is
kept for admin replay.

## Study auto-close

When a Participation saves with `status=COMPLETED`,
`study_closure_signal` runs:

```python
with transaction.atomic():
    study = Study.objects.select_for_update().get(id=...)
    if study.actual_completed_count >= study.target_completed_count:
        study.status = CLOSED
        StudyLink.objects.filter(study=study, is_active=True).update(
            is_active=False
        )
```

`Study.actual_completed_count` is a `@property` backed by an aggregate
`COUNT(*)`, **not** a stored counter. No race.

## Researcher notifications (Inbox)

Three `post_save` handlers write `InboxItem` rows with
`unique_together = (team, kind, ref_kind, ref_id)`:

| Signal | InboxItem.kind |
|---|---|
| `InterviewSession.status = COMPLETED` | `session_completed` |
| `SessionInsight.__init__` | `insight_ready` |
| `Study.status = CLOSED` | `study_completed` |

Second signal fires silently no-op via `get_or_create`.
Frontend InboxPage loads `/api/inbox-items/` and renders with a
mark-read action.

## Observability

### trace_id

Every row on `Invitation / DeliveryRecord / Participation /
InterviewSession / SessionEvent / SessionInsight / InboxItem` carries
a `trace_id`. In a single participant's journey all share one UUID.

`merism.observability.bind_trace(trace_id=...)` is a context manager
that binds the id into structlog's `contextvars` for the duration of
a unit of work:

```python
from merism.observability import bind_trace

with bind_trace(trace_id=session.trace_id, session_id=str(session.id)):
    await stream_turn(session, participant_message=text)
```

All logs emitted inside the block include `trace_id`. Grep
production logs for a trace_id to reconstruct the full path.

### Participation Trail admin view

`/admin/merism/participation/<id>/trail/` aggregates:

- DeliveryRecord rows matching the trace_id
- SessionEvent rows from the bound InterviewSession
- SessionInsight rows

rendered as a chronological timeline. Primary ops triage surface.

## Deliberately not here

- ❌ **Temporal / Restate** — Celery + event log is enough for Merism's scale (45min sessions)
- ❌ **LangGraph / Prefect** — single LLM call per turn; no graph needed
- ❌ **OpenHands `AgentController` + `Runtime`** — moderator has a 4-action enum, not a tool space
- ❌ **Kafka / EventStore** — append-only Postgres rows with `seq` unique constraint give the same semantics
- ❌ **Langfuse / Helicone** — structlog with trace_id + SessionEvent give 95% of the value; add if shadow-eval needs kick in
- ❌ **Independent agent service** — moderator lives in the same process as the WS consumer; no IPC cost

## References

- `merism/conductor/README.md` — module-level docs with test matrix
- `merism/participant/design.md` — participant-side state machine + security
- ADR 0005 — voice pipeline frame architecture
- `merism/tests/test_e2e_automation.py` — one test walking the entire chain with mocked LLM
