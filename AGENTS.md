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

### 4. Two-node interview moderator (decide → generate)

Per `docs/PRODUCT.md` §5.2 — every user turn runs as **two** sequential
LLM calls inside a single `merism.conductor.moderator.stream_turn`
coroutine:

1. `coverage_steer` (non-streaming) returns a structured
   `ModeratorDecision` via function calling.
2. `decision_validator` enforces hard `probe_policy` / `max_probes`
   rules server-side; illegal LLM decisions are rewritten without
   another model call.
3. `generate` (streaming) yields the spoken reply token-by-token to
   TTS / SSE.

Hard limits — do **not** exceed:

- No third LLM call. No macro / meso / micro decision split.
- No persistent policy modules (`coverage_steer` / `engagement` /
  `off_topic` are decision-prompt context, not modules).
- No LangGraph / Prefect / agent-framework wrapping.

If you think the moderator needs more structure, raise it in an ADR
before writing code.

> Note: prior versions of this rule called for a **single** LLM call.
> The 2-node split was introduced in R23 (2026-05-18) to make the
> decision a first-class structured step under PTT mode's ~1s
> latency budget.

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

Environment:

```bash
uv sync                              # install Python deps
source .venv/bin/activate
pnpm --filter merism-frontend install  # frontend deps
docker compose up -d                 # postgres + redis
```

Local dev servers:

- Before starting `manage.py runserver` or `pnpm dev`, clear any stale
  listeners on `8000` and `5173` so you do not keep hitting an old bundle
  or an old Django process.
- If the browser still shows old UI text after edits, verify the port and
  restart the local server before changing code again.

Tests:

```bash
pytest merism/tests                  # Merism-wide unit/smoke
pytest path/to/test.py::TestClass    # single
pytest --changed                     # only changed (with pytest-testmon, optional)
```

Lint:

```bash
ruff check . --fix
ruff format .
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
- Use `TYPE_CHECKING` for type-only imports.
- All imports at module top. No inline imports except to break genuine
  circular deps or inside `TYPE_CHECKING`.
- Do not create empty `__init__.py` files.
- Prefer `parameterized.parameterized.expand` over writing 5 near-identical
  tests.
- Prefer `merism.testing` factories/fakes over hand-rolled `MagicMock` /
  `SimpleNamespace` setups.

### Python tests

- No doc comments on test functions.
- One top-level `class Test...` per logical unit under test.
- Every new model / view / task / tool must ship with a test file in the same
  directory: `test_<module>.py`.

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

`merism_session_event` is the authoritative log of what happened in an
interview. `InterviewSession.moderator_state`, `.transcript`, and
`.decision_log` are **caches** — they can be rebuilt at any time via
`merism.conductor.event_log.reconstruct_state()`. Never write code
that assumes the caches are authoritative (e.g. don't patch
`moderator_state` without also appending an event, or your change will
be silently reverted on the next replay).

Corollary: if you need a new kind of session fact, add a new
`SessionEvent.kind` rather than shoving it into `moderator_state`.

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
