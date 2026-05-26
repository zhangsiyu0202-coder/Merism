# Merism development guide for agents

> This repo is Merism — an AI-moderated qualitative research platform. It has
> **zero PostHog lineage**. Do not import `posthog.*` anywhere. Do not copy
> patterns from the old cutover repo without reading this file first.

## Read-the-right-doc

| Task | Read |
|---|---|
| **Single source of truth for the product** | [`docs/PRODUCT.md`](docs/PRODUCT.md) — any other doc that disagrees with PRODUCT.md is wrong until PRODUCT.md is updated |
| **Runtime architecture / end-to-end automation** | [`docs/RUNTIME.md`](docs/RUNTIME.md) — invite → interview → insight → inbox chain; event sourcing; closure; auto-close |
| Platform requirements / acceptance criteria (EARS) | [`docs/specs/merism-platform/requirements.md`](docs/specs/merism-platform/requirements.md) |
| IM recruitment requirements (EARS) | [`docs/specs/cowagent-im-recruitment/requirements.md`](docs/specs/cowagent-im-recruitment/requirements.md) |
| Design system scope | [`docs/specs/merism-design-system/requirements.md`](docs/specs/merism-design-system/requirements.md) |
| What's done vs what's next | [`docs/ROADMAP.md`](docs/ROADMAP.md) |
| Module-by-module provenance | [`docs/MIGRATION.md`](docs/MIGRATION.md) |
| Architecture decisions | [`docs/adr/`](docs/adr/) — start with ADR 0001 (why Django, not Supabase) |

**Precedence**: when PRODUCT.md and a spec file disagree on a data-model
shape or user flow, PRODUCT.md wins. Open a PR to correct the spec (and
any affected model / view) before merging new code on top of the stale
definition.

## Architecture rules (non-negotiable)

### 1. No PostHog imports

Never `from posthog.* import ...`. We built Merism from scratch specifically
to shed that dependency. A CI test at `merism/tests/test_boundary.py` will
fail if any module leaks.

### 2. `merism_` db_table prefix

Every Merism model must set:

```python
class Meta:
    db_table = "merism_<singular_noun>"
```

Enforced by a test in `merism/tests/test_model_conventions.py`.

### 3. `team_id` on every tenant-data model

Either:

```python
team = models.ForeignKey("merism.Team", on_delete=models.CASCADE)
```

or (for models that might later move to a separate DB):

```python
team_id = models.BigIntegerField(db_index=True)
```

Models without `team_id` must be org-scoped, user-scoped, or instance-global —
**never silently unscoped**.

### 4. Single-engine interview moderator (LangGraph)

Per `docs/PRODUCT.md` §5.2 and ADR 0013 (v1 retirement, 2026-05-23).
All sessions run on `merism.conductor` — a 5-node LangGraph
`StateGraph` (`ask → judge_off | judge_standard | judge_deep → advance →
ask | END`).

Every user turn runs **at most one** LLM call (the judge). No per-session
LLM calls outside the turn loop:

- 1 judge call per turn (returns ``sufficient: bool`` + ``followup: str |
  None`` in a single ``Evaluation`` Pydantic via ``json_mode``).
- 0 LLM calls in ``off`` mode (the ``judge_off`` node is structural; never
  invokes the LLM).
- ``probe_instruction`` is researcher-written prose, embedded verbatim
  in the judge prompt — no session-start rewriting.
- Final-report generation is delegated to the existing post-session
  pipeline (``merism.conductor.post_session`` + ``SessionInsight``
  agents) reading ``InterviewSession.transcript``.

Hard limits — do **not** exceed:

- No second LLM call inside a turn.
- No macro / meso / micro decision split.
- No persistent policy modules.
- All routing functions are pure functions on state — never call the LLM
  to decide flow (Rule 12).

If you think the moderator needs more structure, raise it in an ADR
before writing code.

> History: v1 (`merism.conductor.moderator.stream_turn`, 2-node decide →
> generate) was introduced in R23 (2026-05-18) and retired 2026-05-23
> per ADR 0013. v2 (list interpreter, ADR 0009) lived for two days and
> was superseded by ADR 0012. The active engine is v3 (LangGraph) only.

### 5. DeepSeek + Qwen stack only

- LLM: DeepSeek v3 (chat) / DeepSeek Reasoner (analysis)
- TTS: Qwen CosyVoice (streaming)
- STT: Qwen Paraformer-realtime
- Vision: Qwen-VL-Max

All routed through the OpenAI-compatible client with a `base_url` override.
Do not add new LLM providers without an ADR.

### 6. No ClickHouse, no HogQL, no Kafka

Postgres (with `pgvector` for embeddings) is the only data store. Redis is
the only queue / pub-sub. If you reach for something else, you're wrong.

### 7. Research goal is the North Star

`Study.research_goal: TextField` is the single source of truth for what a
study is about. It anchors every AI step: guide generation, outline review,
moderator system prompt, session analysis, aggregate synthesis, custom
reports, knowledge retrieval. Do not add a multi-goal model. Do not replace
or split the field.

### 8. Frontend: single design-system entry

All new frontend code imports primitives / patterns / tokens from
`~/lib/merism`. Do not introduce arbitrary Tailwind utilities outside the
`merism-*` namespace. See `docs/specs/merism-design-system/`.

## Commands

Daily workflow — prefer `make` targets over remembering individual commands:

```bash
make dev         # start full stack (docker + backend + frontend + doctor)
make status      # what's running? (PIDs from .pids/dev/, port owners)
make stop        # clean shutdown — no zombie processes
make doctor      # 18-check self-diagnostic
make reset       # one-shot recovery (kill stale, clear queues, re-seed)
make reset --hard  # DESTRUCTIVE: drop & recreate the database
```

The launcher (`bin/dev.sh`) writes per-service PIDs to `.pids/dev/` and
**refuses to start a duplicate**, eliminating the zombie-runserver
problem. `bin/doctor.sh` is the source of truth for "is the dev stack
healthy?" — every failure prints a one-line fix hint.

First-time setup:

```bash
make setup                   # uv sync + docker + migrate + seed_dev + smoke
```

Granular targets (when you need just one piece):

```bash
make up / make down                  # docker compose only
make migrate                          # Django migrations
make seed-dev                         # idempotent admin + org membership
make api / make web                   # one service at a time
make worker / make beat               # local Celery (in addition to docker)
```

Tests:

```bash
make test                             # backend pytest + frontend vitest
pytest merism/tests                   # backend unit/smoke
pytest path/to/test.py::TestClass     # single
```

Lint:

```bash
make lint                             # ruff + format + frontend lint/format
ruff check . --fix && ruff format .   # backend only
pyright merism
pnpm --filter merism-frontend typescript:check
pnpm --filter merism-frontend format
```

Build:

```bash
pnpm --filter merism-frontend build
```

OpenAPI types regeneration (after changing serializers / viewsets):

```bash
python manage.py spectacular --file frontend/src/generated/openapi.yml
pnpm --filter merism-frontend codegen
```

## Commits and PRs

Conventional commits. Scope for Merism domains:

- `feat(study)` / `feat(interview)` / `feat(knowledge)` / `feat(recruit)` /
  `feat(report)` / `feat(memai)` / `feat(design-system)` / `feat(realtime)`

Examples:
- `feat(study): add outline review agent function call schema`
- `fix(recruit): handle feishu token refresh race condition`
- `chore(design-system): add StudyCard pattern + stories`

PR description must include:
- **What**: one-line change summary
- **Why**: which Req # from `docs/specs/*/requirements.md` this satisfies
- **Tested**: `pytest merism/tests` + relevant colocated tests passing
- **Breaking**: any schema or API-surface change (include migration file path)

## Rules

### Python

- Type-annotate every function signature (args + return). Avoid `Any`.
- `from __future__ import annotations` at the top of every module —
  enables forward references without quotes.
- Use modern union syntax: `X | Y` / `X | None`, not `Union[X, Y]` /
  `Optional[X]`.
- Import abstract types from `collections.abc`, not `typing`:
  `Iterable / Callable / Awaitable / AsyncIterator / Sequence` etc.
  (`typing.Iterable` is deprecated in 3.9+; ruff `UP035` enforces.)
- Python 3.12 PEP 695 type parameters preferred over `TypeVar` for new
  code: `def sanitize[T](v: T) -> T: ...`.
- Use `TYPE_CHECKING` for type-only imports.
- All imports at module top. No inline imports except to break genuine
  circular deps or inside `TYPE_CHECKING`.
- Do not create empty `__init__.py` files.
- Prefer `parameterized.parameterized.expand` over writing 5 near-identical
  tests.
- Prefer `merism.testing` factories/fakes over hand-rolled `MagicMock` /
  `SimpleNamespace` setups.

### Pydantic v2 schemas

- Every persisted model uses `model_config = ConfigDict(extra="forbid")`.
  Catches accidental drift between schema and storage at validation time.
- Multi-type fields use a discriminated union:
  ```python
  Block = Annotated[BubbleBlock | InputBlock | ..., Field(discriminator="type")]
  ```
  Each variant has a `type: Literal["bubble"]` field. `isinstance` chains
  in execution code are fine; `match` on `type` literal is also fine.
- Reserved Python keywords (`from`, `class`, `type`, ...) get aliased:
  ```python
  from_: EdgeRef = Field(alias="from")
  ```
  Pair with `populate_by_name=True` and serialise with
  `model_dump(by_alias=True)` for JSON storage.
- For round-trip storage, use `model_dump(mode="json", by_alias=True)`
  on dump and `model_validate(...)` on load; the JSON dict goes
  straight into Postgres `JSONField`.
- `extra="forbid"` is also a poor man's router check: failed
  `model_validate` on `moderator_state` payload signals "this is a
  legacy schema" — caller falls back to v1 engine.

### Errors and observability

- LLM failures inside the engine **never raise**. Wrap each call in
  `try/except`, log via `logger.exception("module.action.failed")`,
  emit a `SessionEvent.kind = error` (with `phase=` describing where),
  leave the variable / state unchanged. Downstream Condition blocks
  branch on `is_set / is_empty` for graceful degradation.
- Reserve `EngineError` (and its subclasses) for genuinely
  unrecoverable conditions: schema violations, walk-loop timeout,
  reference resolution failure that should never happen at runtime.
  Raising `EngineError` exits the turn; everything else lands in an
  error event and the engine continues.
- Per-module sentinel exception classes (e.g. `_ReturnMarkAlreadyPending`,
  `_EventEdgeUnresolvable`) are caught at the engine layer and
  converted into `error` events. Do not let them bubble to ORM layers.
- Never `except Exception: pass`. Every except block must either
  (a) re-raise after wrapping, (b) log via `logger.exception`, or
  (c) emit an event capturing what was swallowed.

### Python tests

- No doc comments on test functions; the test name is the spec.
  `test_skip_walks_default_outgoing_no_answer` >
  `test_skip_works`.
- One top-level `class Test...` per logical unit under test (one
  behaviour or one method). Don't use module-level functions for
  related tests — group them.
- Every new model / view / task / tool must ship with a test file in the same
  directory: `test_<module>.py`.
- Async tests need `@pytest.mark.asyncio`. The project's `asyncio_mode
  = auto` in `pytest.ini` is best-effort; the marker is the contract.
- Top of each test file: a `_minimal_xxx() -> Schema` builder fixture,
  reused across cases. Don't repeat 50-line FlowGraph literals in
  every test.
- Live-LLM tests carry `@pytest.mark.merism_llm_live` so CI auto-skips
  unless `MERISM_LLM_API_KEY` is set. Same for `merism_im_live` /
  `merism_storage_live`.
- Chinese fixture text is OK but ruff flags full-width punctuation
  (`，。？！`) as "ambiguous unicode". Use a file-level
  `# ruff: noqa: RUF001, RUF002, RUF003` header instead of disabling
  globally.

### CI gates

- `ruff check .` must pass — no exceptions, even for stylistic rules.
  If a rule is genuinely wrong for the codebase, disable it in
  `pyproject.toml` with a comment explaining why; don't `# noqa`
  case-by-case.
- `ruff format --check .` must pass. Format on save locally; CI
  treats unformatted code as a failure.
- `pyright merism` must pass. Type errors block merge.
- All pytest collection must succeed even with marker-skipped tests
  (the markers don't excuse import errors).

### TypeScript / React

- Kea logic files for all data + state. No `useState` / `useEffect` for
  business logic (only for ephemeral UI like hover state).
- Functional components only.
- Named exports only.
- `camelCase` for identifiers, `PascalCase` for components, `snake_case` for
  Python.
- Import primitives from `~/lib/merism`. No LemonUI.

### Accessibility

- Every primitive must expose proper ARIA (`aria-disabled`, `aria-busy`,
  `aria-describedby` for errors, etc.) — see design-system spec Req 2.
- Every dialog must trap focus and close on Escape unless `dismissible=false`.
- Every form field must have an associated label (visible or sr-only).

## Security

- Encrypt channel credentials with Fernet before database storage
  (`merism.recruitment.crypto`). Raw secrets never leave
  `ChannelConfig.credentials_encrypted`.
- Validate all incoming public-participant input with DRF serializers.
  Participant routes are **unauthenticated** and thus the primary attack
  surface.
- Rate-limit the IM recruitment dispatch (100 msgs/channel/hour per spec
  Req 7.5).
- Do not log sensitive information — no PII, no auth tokens, no channel
  secrets. Structured logs go through `structlog` so values can be
  inspected at source.

## AI-specific conventions

- LLM calls go through `merism.memai.llm.get_llm()` (OpenAI-compat, DeepSeek
  by default, Anthropic via flag). This centralizes cost / trace recording.
- In Celery tasks, use `merism.memai.capture.scoped_capture` context manager
  — never `capture()` directly in a task (events get silently dropped).
- Payloads crossing Temporal activity boundaries must stay under ~256KB —
  if larger, persist to Postgres / S3 and pass references.

## Agent automation

Prefer automated enforcement over doc rules. Order of preference:

1. Ruff rules + pre-commit hooks
2. Test-level guards (see `merism/tests/test_boundary.py`,
   `test_model_conventions.py`, `test_no_posthog_test_harness.py`)
3. This document

### 9. Event sourcing is authoritative, caches are not

`merism_session_event` is the authoritative log of what happened in a
**v1 interview**. `InterviewSession.moderator_state`, `.transcript`, and
`.decision_log` are **caches** — they can be rebuilt at any time via
`merism.conductor.event_log.reconstruct_state()`. Never write v1 code
that assumes the caches are authoritative (e.g. don't patch
`moderator_state` without also appending an event, or your change will
be silently reverted on the next replay).

Corollary (v1): if you need a new kind of session fact, add a new
`SessionEvent.kind` rather than shoving it into `moderator_state`.

**v3 exception (per ADR 0012)**: `merism_session_event` is **not** the
runtime authority for v3 sessions. LangGraph's checkpoint table is.
The final transcript + report land on `InterviewSession.transcript` +
`moderator_state.final_report` once at session end via
`merism.conductor.persistence.finalize_to_session`. Existing
analytics / report code reads `InterviewSession.transcript` unchanged.
If a future requirement needs event-level granularity for v3, add a
checkpoint→event mirror sink rather than rewiring the engine.

### 10. `trace_id` binds the chain end-to-end

Every row on `Invitation / DeliveryRecord / Participation /
InterviewSession / SessionEvent / SessionInsight / InboxItem` carries
a `trace_id`. All rows in one participant's journey share one UUID.
New tables that sit on this path must have a `trace_id: UUIDField`
populated from the upstream row at insertion time.

New code that logs interesting facts should run inside a
`merism.observability.bind_trace(trace_id=...)` block so structlog
picks it up automatically.

### 11. Study completion is an aggregate, not a counter

`Study.actual_completed_count` is a `@property` that runs
`Participation.objects.filter(status=COMPLETED).count()`, not a
stored field. This is by design to avoid race-prone `+= 1` signal
handlers. Admin / API code that wants the value without N+1 should
use `Study.annotate_completed_count()`.

### 12. AI is content-only; flow control is rule-driven

Per ADR 0012 (`docs/adr/0012-conductor-v3-langgraph.md`) and
`docs/specs/conductor-v3/`. In `merism.conductor`:

- LLM produces **structured slot values** (via Pydantic
  `with_structured_output(method="json_mode")`) and **prose text**
  (probe questions, final report). It never decides "next node".
- All flow decisions — probe vs advance, mode dispatch, end of outline
  — are **pure routing functions** evaluated by LangGraph's
  `add_conditional_edges`. ``route_after_ask / route_after_judge /
  route_after_advance`` are functions of state, not of LLM output.
- The judge node returns ``Evaluation(sufficient: bool, missing: list,
  followup: str | None, reason: str)``. The engine's pure
  ``route_after_judge`` reads ``state["pending_probe"]`` (set when the
  engine accepts the LLM's followup, capped by budget) and dispatches.
- Researchers write a flat list of questions per section. The graph
  topology is fixed (7 nodes); only the data changes per outline.

If you find yourself adding "the LLM should also decide X" or "let's
have the AI return a `next_action` field", stop. That's how v1 / v2
went; v3 keeps the line clean.

### 13. Single-engine moderator — v1/v2 fully retired

Per ADR 0013 (2026-05-23). The interview moderator is a single
LangGraph engine living in `merism.conductor`. There is no engine
selector, no version branching at runtime.

- Outlines validate against the v3 Pydantic schema
  (``Outline.version: Literal["v3"]``). The literal is a **content
  schema discriminator** — kept for forward compatibility if a v4
  shape is ever introduced — not an engine version.
- New code imports from `merism.conductor`. The previous
  `merism.conductor_v3` package was merged into `merism.conductor`
  on 2026-05-24; `merism.conductor_v2` was deleted earlier (ADR 0012);
  v1 (`merism.conductor.moderator`) was deleted with ADR 0013.
- The legacy `migrate_guide_to_v3` command was deleted on 2026-05-24
  after the dev DB was fully migrated. If you ever need to convert v1
  list-shape guides again, restore from git history.
  functionality. Cross-engine imports are no longer a concern (no other
  engines exist).


## Engine architecture (Conductor v3)

Conventions baked in during `merism/conductor/` development per
ADR 0012. They generalise — apply to any new "engine"-shaped module
(analysis pipeline, recruitment dispatcher, etc.).

### Pure functions over orchestrators

- The engine is a LangGraph `StateGraph` whose nodes are pure-ish
  functions over typed state (`OverallState`). Real work lives in
  one-concept-per-module files:
  `schema.py / state.py / configuration.py / tools_and_schemas.py /
  prompts.py / llm.py / nodes.py / graph.py / runner.py /
  persistence.py / router.py / text_adapter.py`.
  Each does one thing in 50-300 LOC.
- Helper modules import only `schema` + `state` + Pydantic + each other.
  Only `persistence.py` imports Django ORM (the bridge to
  `InterviewSession`); every other v3 module is ORM-free for
  unit-testability.
  events.
- The orchestrator (`engine.py`) glues helpers together and handles
  control flow. It does not duplicate helper logic.

### Dependency injection over import for IO

- LLM calls, event sinks, transcript loaders are passed as callable
  parameters. Never imported at engine module level.
  ```python
  async def walk_flow_forward(
      ..., *,
      ai_extract_fn: AIExtractFn | None = None,
      ai_generate_fn: AIGenerateFn | None = None,
      event_sink: EventSink | None = None,
      transcript_loader: TranscriptLoader | None = None,
  ): ...
  ```
- Mock LLM fns are trivially injected for tests. Real DeepSeek /
  Qwen adapters live in a separate `ai_clients.py` module that knows
  how to build them.
- Same for ORM: engine never `from merism.models import ...`. Voice
  consumer / API view layers do the ORM round-trip and pass plain
  Pydantic state in / out.

### Immutable state, returns over mutation

- `SessionState` is treated as immutable. Every state transition uses
  `state.model_copy(update={...})` or `model_copy(deep=True)` and
  returns a new instance.
- Never mutate state objects passed in as arguments. The engine
  returns a `WalkResult` containing the new state; caller is
  responsible for persisting.

### Events first, then state

- For every state mutation, emit the corresponding `SessionEvent`
  *before* committing the new state. This guarantees Rule 9 (event
  log is authoritative): even if persistence fails after the event
  write, the next replay rebuilds the same state.
- `event_sink` is the single write path. `_emit_event` swallows
  event-sink exceptions and logs them — event I/O failure must never
  abort flow.

### Module file conventions

- Public functions: `verb_noun` (`execute_invalid_reply_event`,
  `walk_flow_forward`).
- Private helpers: `_verb_noun` prefix (`_dispatch_command_event`,
  `_record_answer`).
- `find_X` returns `X | None`; `get_X` raises if missing; `lookup_X`
  is reserved for private finds.
- Constants in `SCREAMING_SNAKE` at the top of the module, after
  imports.
- `__all__` at the end, sorted alphabetically (ruff `RUF022`).
  Group via blank lines + comments only when the natural sort would
  obscure structure.

### Documentation in code

- Module docstring explains *why* + cites the spec / requirement
  number. Not "this module does X".
- Class docstring explains lifecycle + who is responsible for
  updating fields. Especially for persisted models.
- Inline comments explain *why this code path* over alternatives. Do
  not narrate what the code does — read the code for that.
- TODOs cite a phase or ER number: `# TODO(P1.5): wire ReturnBlock`
  not `# TODO: later`.

### Explicit subset of what NOT to do

- Don't `def f(*args, **kwargs)` unless the wrapped callable's
  signature genuinely varies. Type-annotated args are documentation.
- Don't sprinkle `# type: ignore` to silence pyright. Fix the type
  or restructure the code.
- Don't import from `merism.conductor` inside `merism.conductor`
  (Rule 13). Carry the helper over or rewrite it.
- Don't add LLM providers / queues / data stores without an ADR
  (Rules 5, 6).
- Don't write to `moderator_state` without also appending an event
  (Rule 9). Caches are derived; events are authoritative.
