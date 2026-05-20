# Merism rebuild roadmap

This doc tracks every task for the clean-slate rebuild under `merism-app/`.
Each section is "done" / "next" / "later".

## ✅ Done (R1-R4, R6, R7, R8 skeleton, R10)

### R1 — Bootstrap files
- `pyproject.toml` — Python 3.12.12 pin, Django 5.2.13, DRF, pgvector,
  pydantic v2, cryptography, openai (DeepSeek-compat), langchain-core, structlog
- `README.md`, `AGENTS.md` (trimmed, Merism-only, 8 non-negotiable rules)
- `docker-compose.yml` — postgres (pgvector) + redis + minio. No ClickHouse /
  Kafka / Temporal.
- `bin/setup-dev.sh` + `bin/postgres-init.sql` — one-command idempotent setup
- `manage.py`, `.gitignore`, `.env.example`, `pytest.ini`, `conftest.py`

### R2 — Django project skeleton
- `merism/{__init__,apps}.py`
- `merism/settings/{__init__,base,dev,test,prod}.py` (prod asserts required
  env vars via `ImproperlyConfigured`)
- `merism/{urls,wsgi,asgi}.py`

### R3 — Test harness
- `merism/testing/` — 24 files ported verbatim from the old repo
  (factories, fakes, assertions, fixtures, freezetime, pytest_plugin)
- `merism/tests/test_boundary.py` — new boundary tests asserting
  `DJANGO_SETTINGS_MODULE=merism.settings.test`, no `posthog` package
  importable, no `posthog.*` in `sys.modules`, `INSTALLED_APPS` is
  Merism-only

### R4 — Core models (27 models across 8 files)
- `merism/models/team.py`        — `Organization`, `OrganizationMembership`,
  `Team`, `TimestampedModel`, `UUIDModel`, `team_id_field`
- `merism/models/study.py`       — `Study` (with `research_goal: TextField`
  single value per spec), `StudyLink`, `StudyTemplate`, `StudyTrigger`
- `merism/models/stimulus.py`    — `Screener`, `Stimulus`
- `merism/models/interview.py`   — `InterviewGuide`, `Participant`,
  `Participation` (includes `is_preview`), `InterviewSession` (voice/video
  modes per spec Req 12), `InterviewRecording`
- `merism/models/knowledge.py`   — `TeamResearchKnowledgeBase` (L1),
  `StudyKnowledgeBase` (L2), `KnowledgeDocument`, `KnowledgeChunk`
  (pgvector `VectorField` + sqlite JSONField fallback, `EMBEDDING_DIM=1536`)
- `merism/models/recruitment.py` — `ChannelConfig` (Fernet-encrypted creds),
  `MessageTemplate`, `RecruitmentBroadcast`, `DeliveryRecord`,
  `ChannelHealthCheck`
- `merism/models/report.py`      — `SessionInsight`, `AggregateSynthesis`,
  `StudyReport`, `CustomReportQuery`
- `merism/models/memory.py`      — `Conversation`, `AgentMemory`,
  `CoreMemory`
- `merism/models/__init__.py`    — flat re-export

Conventions enforced:
- every model has `db_table = "merism_<noun>"`
- every tenant-data model has `team` FK to `merism.Team`
- `StudyGoal` multi-goal flat list is deliberately **not** created (spec Req
  21.3/21.4 mandates a single `Study.research_goal` TextField)

### R6 — IMChannel port (done)
Ported from `products/studies/backend/recruitment/` with
`products.studies.backend.recruitment.channels.*` imports rewritten to
`merism.recruitment.adapters.*`:

- `merism/recruitment/adapters/{base,feishu_adapter,wecom_bot_adapter,qq_group_adapter,qq_guild_adapter,factory}.py`
- `merism/recruitment/crypto.py` — Fernet encrypt/decrypt (now prefers
  `MERISM_CHANNEL_ENCRYPTION_KEY` env, falls back to PBKDF2-on-SECRET_KEY)
- `merism/recruitment/renderer.py` — placeholder rendering + per-channel payload shaping
- `merism/recruitment/rate_limit.py` — 100msg/channel/hour cap
- `merism/recruitment/builtin_templates.py` — system-owned template seeds
- `merism/recruitment/__init__.py` — public barrel
- `merism/recruitment/README.md` — ported vs TODO tasks

Verified zero `posthog.*` / `products.*` imports remain.

### R7 — Report block schema (done)
- `merism/reports/schema.py` — Pydantic v2 models:
  - block atoms: `TextBlock` / `QuoteBlock` / `MetricBlock` / `ChartBlock`
  - flat doc: `BlocksDocument` + `validate_blocks_list()`
  - 4-panel (per PRODUCT.md §4): `StudyReportContent` +
    `validate_study_report_content()`
  - `ChartSpec` / `Citation` / `CustomReportAnswer` — Custom Report
    function-calling output shape
- `merism/reports/tests/test_schema.py` — 18 tests covering atoms,
  discriminator, panel rejects (quant_panel rejects quote blocks;
  qual_panel rejects metric blocks), empty-default roundtrips
- `merism/reports/__init__.py` — public exports

### R8 — Domain skeletons (done)

All domain packages now have their runners or interfaces in place.

| Package | Done |
|---|---|
| `merism/api/` | **R12**: full DRF layer — `base.py` (TeamScopedModelViewSet + get_team()), `serializers.py` (22 serializers), `views.py` (17 viewsets + 10 @actions like launch/close/finalize/search/test/send/retry), `urls.py` mounting all at `/api/` |
| `merism/conductor/` | `state.py` (ExecutionState), `prompts.py` (ModeratorDecision + build_system_prompt), **R12**: `moderator.py` (single-call streaming runner per PRODUCT.md §5.2), `guide_cursor.py` (pure traversal helpers) |
| `merism/memai/` | `tool.py` (MemTool abstract base), **R12**: `llm.py` v2 with Langfuse auto-instrumentation (no-op when keys absent) |
| `merism/knowledge/` | `citations.py`, **R12**: `search.py` (pgvector cosine + Postgres ts_rank_cd BM25 + RRF k=60 fusion), `embeddings.py` (DeepSeek client with auto-fallback) |
| `merism/realtime/` | SSE: `sse_interview.py` (Redis Streams + Last-Event-ID replay + 15s heartbeat + 5000-event maxlen), **R13**: WebSocket: `voice_protocol.py` (strict Pydantic messages) + `voice.py` (Channels consumer with STT↔moderator↔TTS orchestration + ADR-0002 barge-in) + `routing.py` |
| `merism/recruitment/` | **R12**: `tasks.py` (dispatch_recruitment_delivery with rate limit + per-delivery outcome / retry_failed_deliveries / health_check_channels beat every 30min) |
| `merism/reports/` | `schema.py` (block atoms + StudyReportContent 4-panel + ChartSpec + Citation + CustomReportAnswer) with 18 tests |
| `merism/stt.py` / `tts.py` / `vision.py` | Client skeletons — raise without API key to force fake substitution in tests |
Ported from `products/studies/backend/recruitment/` with
`products.studies.backend.recruitment.channels.*` imports rewritten to
`merism.recruitment.adapters.*`:

- `merism/recruitment/adapters/{base,feishu_adapter,wecom_bot_adapter,qq_group_adapter,qq_guild_adapter,factory}.py`
- `merism/recruitment/crypto.py` — Fernet encrypt/decrypt (now prefers
  `MERISM_CHANNEL_ENCRYPTION_KEY` env, falls back to PBKDF2-on-SECRET_KEY)
- `merism/recruitment/renderer.py` — placeholder rendering + per-channel payload shaping
- `merism/recruitment/rate_limit.py` — 100msg/channel/hour cap
- `merism/recruitment/builtin_templates.py` — system-owned template seeds
- `merism/recruitment/__init__.py` — public barrel
- `merism/recruitment/README.md` — ported vs TODO tasks

Verified zero `posthog.*` / `products.*` imports remain.

### R10 partial — docs
- `docs/PRODUCT.md` — copied from `standalone/PRODUCT.md`
- `docs/specs/cowagent-im-recruitment/` — full copy of `.kiro/specs/`
- `docs/specs/merism-design-system/` — full copy
- `docs/specs/merism-platform/` — full copy
- `docs/ROADMAP.md` — this file
- `docs/MIGRATION.md` — see below

---

## ⏳ Next (R5, R7, R8, R9, R11)

### R5 — Initial Django migration
```bash
source .venv/bin/activate
python manage.py makemigrations merism
python manage.py migrate
```
Expected output: one initial migration creating all 27 tables + pgvector
extension enable (via `pgvector.django.VectorExtension`).

Gotcha: the `VectorField` import in `merism/models/knowledge.py` falls back
to `JSONField` when `pgvector` can't be imported. In test env this is fine
(sqlite doesn't support vector anyway). For prod you MUST have
`CREATE EXTENSION vector;` run — `bin/postgres-init.sql` does this on first
container start, but if you already have a database without it, run:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### R7 — Report block schema
Port `products/studies/backend/reports/schema.py` (Pydantic v2) to
`merism/reports/schema.py`:

- `BlocksDocument` (the outer doc shape)
- Inner block types: `TextBlock`, `MetricBlock`, `QuoteBlock`, `ChartBlock`
- `validate_blocks_list(data)`
- Tests at `merism/reports/tests/test_schema.py`

Also add:
- `StudyReportContent` — the **4-panel structured shape** per
  PRODUCT.md §4 and merism-platform Req 17:
  ```python
  class StudyReportContent(BaseModel):
      exec_summary: str
      quant_panel: list[ChartBlock | MetricBlock]
      qual_panel: list[QuoteBlock | TextBlock]
      insight_nuggets: list[MetricBlock]
  ```
- `ChartSpec` — the shape charts render from (`{type, title, x, y, unit, ...}`)

~2 hours work (models + validator + tests).

### R8 — Remaining domain skeletons

Each gets an `__init__.py`, a `README.md` with task list, and the minimum
necessary files.

#### Port-don't-rewrite (PRODUCT.md §7 — Phase 0 reusables)

These exist in the old repo and PRODUCT.md explicitly says reuse them
unchanged, just de-PostHog'd:

| Source (old repo) | Destination (merism-app) |
|---|---|
| `products/studies/backend/guide_generator.py` | `merism/studies/guide_generator.py` |
| `products/studies/backend/analysis.py`        | `merism/studies/analysis.py`        |
| `products/studies/backend/api.py` (StudyViewSet + actions) | `merism/api/studies.py` |

Port pattern: `cp` → rewrite `from posthog.*` / `from products.studies.*`
imports → replace ``posthog.Team`` FK refs with `merism.Team` / the new
models — same pattern we used for IMChannel in R6.

#### `merism/conductor/` — single-call interview moderator
- `state.py` — Pydantic v2 `InterviewState` (copy/adapt
  `merism/conductor/state.py` from old repo)
- `moderator.py` — **single LLM call** returning `(text, next_action)` per
  platform Req 14. Do NOT implement macro/meso/micro layers. Do NOT
  implement policies.
- `prompts.py` — moderator system prompt builder
- `tests/`
- Drop: `merism/conductor/macro.py`'s LangGraph multi-node graph — the spec
  explicitly forbids this split.

#### `merism/knowledge/` — RAG, no HogQL
- `indexer.py` — chunk + embed pipeline (called async after session ends)
- `search.py` — hybrid BM25 + pgvector cosine (`SELECT ... ORDER BY embedding <=> %s`)
- `citations.py` — port from `products/studies/backend/knowledge_citations.py`
- `tests/`
- Drop anything that references `posthog.hogql`.

#### `merism/memai/` — Merism-native AI tools (NOT PostHog's hogai)
Complete redesign. Only keep the tool *base class* pattern from the old
repo. Throw out every PostHog-product-specific tool.

- `tool.py` — thin `MemTool` abstract base (LangChain `BaseTool` compatible)
- `llm.py` — `get_llm()` wrapping `openai.OpenAI` with `base_url` pointed at
  DeepSeek (or Anthropic if flag set)
- `tools/search_research.py` — semantic search over the team's studies
- `tools/compare_personas.py` — cross-persona analysis
- `tools/analyze_interviews.py` — ad-hoc multi-session analysis
- `tools/recruitment_plan.py` / `recruitment_draft_copy.py` /
  `recruitment_preview.py` / `recruitment_send.py` / `recruitment_status.py`
  — the 5 recruitment tools already reserved in the spec
- `agents/ask_merism.py` — Ask Merism chat runner (single agent, no mode
  switching)
- `rag/` — borrow index/retrieval from `merism.knowledge`

#### `merism/realtime/` — SSE + WebSocket
- `sse_interview.py` — SSE stream producer for interview replay
- `ws_voice_protocol.py` — WebSocket voice protocol (participant audio in,
  AI audio out)
- Redis Streams for replay backbone

#### `merism/stt.py / tts.py / vision.py`
Port `products/studies/backend/stt.py` / `tts.py` / `vision.py` with the
PostHog-specific imports removed. These are thin HTTP clients against
DashScope (Paraformer + CosyVoice + Qwen-VL).

### R9 — Frontend bootstrap + design system

Full scope is in `docs/specs/merism-design-system/`. For skeleton:

- `frontend/package.json` — pnpm workspace
- `frontend/vite.config.ts` — Vite + React + TS
- `frontend/tsconfig.json`
- `frontend/index.html`
- `frontend/src/main.tsx` — root app
- `frontend/src/design_system/tokens/{colors,typography,spacing,shadows,radii,breakpoints}.ts` — ports from `frontend/src/lib/merism/tokens/` in old repo
- `frontend/src/design_system/primitives/{Button,Card,Input,Tag,StatusDot,Tooltip,Dialog,Tabs}.tsx`
- `frontend/src/design_system/patterns/{PageShell,TabBar,StudyCard,SessionRow,ChatPanel}.tsx`
- `frontend/src/design_system/fonts/` — Inter, Geist eager; Plex Mono lazy
- `frontend/src/app/` — auth shell, top-level routes
- `frontend/tailwind.config.js` — `merism-*` namespace

Storybook scaffolding deferred to later — not a blocker.

### R11 — Verification
```bash
bin/setup-dev.sh             # must exit 0
pytest merism/tests          # all smoke tests pass
python manage.py check       # no Django errors
ruff check merism            # no lint errors
pyright merism               # no type errors
```

---

## 🔭 Later (post-MVP)

- **Codebook Governance (R16)**: Full codebook lifecycle subsystem — in progress.
  - ✅ Design doc: `docs/specs/codebook-governance/design.md`
  - ✅ Data models: `CodebookVersion`, `CodeChange`, `CodeMapping`
  - ✅ `InductiveCodeSuggester` agent (batch emergent code discovery)
  - ✅ `CodebookReviewer` agent (merge/split/rename/deprecate proposals)
  - ✅ `CodebookVersionManager` (immutable snapshots + mappings)
  - ✅ `RetaggingJob` (selective re-tagging of affected quotes)
  - ✅ `ThemeSynthesizer` auto-trigger (saturation + target_reached)
  - ✅ Pipeline integration in `post_session.py`
  - ⬜ Frontend: codebook version history + proposal approve/reject UI
  - ⬜ Admin: CodebookVersion / CodeChange browsing
- **Dagster or Temporal**: The platform spec doesn't decide. Default to
  Celery + Celery Beat for now. Revisit when cross-DAG workflows become
  necessary.
- **Dark mode**: Tokens already have `semanticDark`; primitives use CSS
  vars. Visual tuning needed.
- **Frontend Kea → Jotai?**: Old repo was Kea-heavy. Evaluate in R9
  whether to keep Kea or move to Jotai + Tanstack Query for simplicity.
  Decision can wait until we have 5+ connected views.
- **Stimuli S3 upload flow**: Req 6.5 says S3 via PostHog's abstraction.
  We need a Merism-native equivalent — probably just `boto3` + signed URL.
- **i18n**: `InterviewSession.locale` is already a field. Deliver i18n
  once English flow is green.

---

## Commit plan

Commits are small and atomic. Today's sequence:

1. `chore(rebuild): scaffold merism-app bootstrap` — R1+R2
2. `chore(rebuild): port merism.testing and boundary tests` — R3
3. `feat(models): add merism core models with merism_ prefix` — R4
4. `feat(recruit): port IMChannel adapters + crypto + renderer` — R6
5. `docs(rebuild): add ROADMAP, MIGRATION, copy specs` — R10

Then stop and let the developer review before R5/R7-R9.


---

## ✅ R14 — Outset-grade UX overhaul (2026-05-10)

A front-to-back visual + architectural pass that takes the app from "functional
MVP" to "Outset.ai-grade research workbench". Six major threads, all completed
in a single sitting with a zero-regression bar (`pytest 59 passed · frontend
37 passed · build < 5s` at every checkpoint).

### R14.1 — Concept Testing 2.0 (carry-overs from R13)
- Per-concept section rotation (`Concept` + `ConceptBlock` + `ConceptRotationCursor`)
  with three strategies (fixed / random_per_session / **persistent latin-square**).
- `concept_plan.expand_guide()` as pure function + `moderator._expand_if_needed`
  advances cursor atomically via `F("position") + 1` for latin_square blocks.
- `StimulusShowFrame` + `WebSocketEgressObserver` bridge to
  `StimulusShowMessage` — frontend crossfades concept preview image on transition.
- Dimensions scorer (`merism/concept/dimensions.py`, 146 LOC):
  sentiment / purchase_intent / appeal / comprehension — weights by transcript
  turns buckets via `{question_id, concept_id}` tagging. Winner tiebreak:
  `purchase_intent → appeal → sentiment → sessions_seen`.
- `ConceptBlockViewSet.report` action returns `dimensions[]` per concept.

### R14.2 — Design token system overhaul (8pt grid + Slate)
- **Neutrals**: warm Cohere paper → cool Slate (`#F9FAFB` / `#0F172A` /
  `#64748B` / `#E2E8F0`).
- **Typography**: 10-tier strict 8pt-aligned scale
  (`hero 72 · display 48 · headline 32 · h2 24 · title 20 · subtitle 18 ·
  body 16 · body-sm 14 · label 13 · caption 12 · mono 13`).
- **Radii**: `xs 4 · sm 6 · md 8 · lg 12 · xl 16 · 2xl 24 · full 9999`.
- **Elevation**: `shadow-merism-xs / sm / card / float / pop` — diffuse
  rgba(15,23,42,α) shadows replace solid borders on all cards.
- **Hairline**: `--merism-hairline` (rgba 0.06) for "invisible structure".
- **4 tracking tokens**: `caps` / `caps-tight` / `tight` / `display`.
- **Tag palette**: Stripe-grade same-hue alpha-core system —
  `--merism-status-{neutral|accent|success|warning|danger|info}` core + matching
  `-bg` at 8-9% alpha. **No pastel fills, no solid borders anywhere.**
- **Global scrollbar**: thin (6px), invisible track, 10%→25% thumb on hover,
  WebKit + Firefox, dark-mode automatic.
- **Global font-smoothing**: `antialiased` + explicit webkit/moz overrides.
- **bin/align_8pt.py**: repeatable migration script (75 spacing + 22 text-size
  fixes applied) — safe to re-run.

### R14.3 — Design-system primitives

All new / rewritten components live under `frontend/src/lib/merism/{primitives,patterns}/`:

| Pattern | Purpose | LOC |
|---|---|---|
| `PageTopBar` | Per-scene masthead (title + status tag + actions + tabs) | 73 |
| `PageHeading` | H1 block — 32px/medium, asymmetric vertical rhythm | 96 |
| `KpiCard` / `KpiGrid` | Editorial big-number cards (5-col responsive) | 168 + 54 |
| `ExecutiveSummary` | Narrative hero with LLM-stream skeleton | 138 |
| `SettingsSection` | Editable section block (H2 + body + Edit action) | 95 |
| `OrderedList` | Numbered editorial list (read/editable) | 187 |
| `ThreePaneLayout` / `LogicCard` / `LiveSummaryPanel` | Editor primitives | 59 + 91 + 101 |
| `Illustration` | Notioly SVG themed via `currentColor` | 87 |
| `ChatPanel` | Glass AI bubble + 24px ink send button (rewrite) | 227 |
| `Tag` (primitive) | Same-hue alpha-core + 5px dot + unified inset edge | 193 |

Storybook stories for every new pattern (Catalog / SizeLadder / Theming /
InEmptyState / etc.).

### R14.4 — Sidebar architecture (Outset four-zone)
Replaced abstract "Workspace / Library" group headers with a flat entity
navigation:

| Zone | Component | Behaviour |
|---|---|---|
| 1 | `WorkspaceAnchor` | Team name + chevron (click → /settings) |
| 2 | Flat entity nav | Home · Studies · Ask · Inbox · Repository · Decisions |
| 3 | `PinnedStudies` | localStorage-backed max-3 recent + inline "New study" |
| 4 | `UserBadge` + Settings | Avatar + name + email + sign out |

`sidebarLogic.ts` uses a `touchStudy` listener on `sceneLogic.setScene` so the
current study auto-pins whenever the user navigates in.

### R14.5 — Home scene
New `Scene.Home` at `/` (was mapped to Ask) with:
- 5-column KpiGrid (Sessions · Studies · Talk time · Participants · Insights)
  served by `GET /api/home/stats/`.
- Horizontal `StudyCard` strip + tail "+ Start a new study" card.
- `FirstStudyHero` illustration-backed empty state.
- Overview / Activity / Drafts sub-tabs (Overview implemented).

### R14.6 — Settings scene + model change
- **Backend**: `Study.research_objectives: JSONField(default=list)` added —
  migration `0004_study_research_objectives` applied. North-Star
  `research_goal` kept single-line (AI anchor).
- **Frontend**: `/studies/:id/settings` — SettingsSection + OrderedList
  composition, per-section edit mode via `studySettingsLogic`.
- **Security fix**: `TeamScopedModelViewSet.perform_create` now always
  injects `team` when model has `team_id` (was only when serializer exposed
  the field). Closed the `POST /api/studies/` null-team path.

### R14.7 — Per-page sub-nav + illustration wiring
`PageTopBar` applied to all 7 top-level pages with matching tab sets:

| Page | Tabs (default bold) | Illustration (empty state) |
|---|---|---|
| Home | **Overview** · Activity · Drafts | `planning-a-trip` (xl) |
| Studies | **All** · Active · Drafts · Archived | `jumping` (xl) |
| Ask | **Chat** · History · Saved | `fast-internet` (md) |
| Inbox | **All** · Unread · Flagged | `chill-time` (xl) |
| Repository | **Documents** · Chunks · Templates | `painting` (xl) |
| Decisions | **Open** · Closed · Linked | `flag` (xl) |
| Settings (workspace) | — | — |

Studies page: `active/drafts/archived` filters are real (client-side
`visibleStudies` slicing); `all` uses same data as the list page did.

### R14.8 — Header compaction (last pass)
- `PageHeading` title: 48px display → 32px headline · weight 450 → 500.
- Internal rhythm: asymmetric gaps (eyebrow 8 / title 8 / lede 24).
- Inline `status` slot baseline-aligned with title (replaces right-side tag).
- `AppLayout` top padding: 72 → 24px (`--spacing-merism-page-top` retained
  as token for future marketing heroes but no longer applied in app shell).
- Top-level pages outer `gap-section-y` (64) → `gap-8` (32). Inside-page
  section-y (Home Overview between KPI row and Studies strip) retained.

**Net vertical-space reclaim:** ~80px per scene — from TopBar edge to
first interactive element.

### Verification at final checkpoint

```
backend pytest : 59 passed + 1 skipped
frontend       : typecheck 0 · vitest 37 · oxlint 0 · vite build 3.6s
kea typegen    : 21 logics
storybook      : HMR live on :6006
API smoke test : GET /api/home/stats/ → 200 · POST /api/studies/ → 201
```

### Files touched this sprint

~50 files modified/created. Highlights:

**Backend (7 files)**
- `merism/api/home.py` (new) · `merism/api/base.py` (security fix) ·
  `merism/api/urls.py` · `merism/api/serializers.py` ·
  `merism/models/study.py` · `merism/migrations/0004_*`.

**Frontend design system (16 files)**
- `lib/merism/{tokens/variables,tokens/theme,fonts/preload}.css` ·
  `lib/merism/primitives/{Tag,Card,Button,Input,Dialog}.tsx` ·
  `lib/merism/patterns/{KpiCard,KpiGrid,ExecutiveSummary,LogicCard,
  LiveSummaryPanel,ObjectiveList,SettingsSection,OrderedList,PageTopBar,
  ThreePaneLayout,ChatPanel,PageHeading}.tsx` ·
  `lib/merism/illustrations/{Illustration.tsx,svg/*.svg}` · Storybook
  stories for every new component.

**Frontend scenes (10 files)**
- `features/{home,studies,ask,inbox,repository,decisions}/...` +
  `features/studies/tabs/{settings,outline,screener,stimuli}/...`.

**Infra**
- `bin/align_8pt.py` — repeatable 4pt-grid migration script.
- `.gitignore` — excludes raw illustration pack.


---

## ✅ R14 — Outset-grade UX overhaul (2026-05-10)

A front-to-back visual + architectural pass that takes the app from "functional
MVP" to "Outset.ai-grade research workbench". Eight threads, all completed
with a zero-regression bar (`pytest 59 passed · frontend 37 passed · build < 5s`
at every checkpoint).

### R14.1 — Concept Testing 2.0 finalization

- Per-concept section rotation (`Concept` / `ConceptBlock` /
  `ConceptRotationCursor`) with three strategies — the key one being
  **persistent latin-square** via `F("position") + 1` atomic advance.
- `concept_plan.expand_guide()` pure function + `moderator._expand_if_needed`.
- `StimulusShowFrame` → `WebSocketEgressObserver` → `StimulusShowMessage` —
  frontend crossfades preview image on transition.
- Dimensions scorer (`merism/concept/dimensions.py`) scores sentiment /
  purchase_intent / appeal / comprehension per concept; tiebreak
  `purchase_intent → appeal → sentiment → sessions_seen`.
- `ConceptBlockViewSet.report` returns `dimensions[]` per concept.

### R14.2 — Design-token overhaul (8pt grid + Slate + Stripe algorithm)

- **Neutrals**: warm Cohere paper → cool Slate (`#F9FAFB` / `#0F172A` /
  `#64748B` / `#E2E8F0`).
- **Typography**: 10-tier strict 8pt-aligned scale
  (hero 72 · display 48 · headline 32 · h2 24 · title 20 · subtitle 18 ·
  body 16 · body-sm 14 · label 13 · caption 12 · mono 13).
- **Radii**: xs 4 · sm 6 · md 8 · lg 12 · xl 16 · 2xl 24 · full 9999.
- **Elevation**: `shadow-merism-xs / sm / card / float / pop` — diffuse
  rgba(15,23,42,α) shadows replace solid borders on every card surface.
- **Hairline**: `--merism-hairline` (rgba 0.06) + `-strong` (0.1) for
  "invisible structure".
- **Tracking**: 4 new tokens (`caps` / `caps-tight` / `tight` / `display`).
- **Tag palette**: Stripe-grade same-hue **alpha-core** algorithm —
  `--merism-status-{neutral|accent|success|warning|danger|info}` one core
  colour + `-bg` at 8-9% alpha. Zero pastel fills, zero solid borders,
  unified 1px inset edge (`--merism-status-edge`) across all variants.
- **Scrollbar**: thin (6px) global, invisible track, 10%→25% thumb-on-hover,
  WebKit + Firefox, dark-mode flipping via CSS vars.
- **Font-smoothing**: global `antialiased` + explicit webkit/moz overrides.
- **`bin/align_8pt.py`**: repeatable migration script (75 spacing + 22
  text-size fixes applied) — safe to re-run.

### R14.3 — Primitives + patterns built or rewritten

| Component | Role | LOC |
|---|---|---|
| `PageTopBar` | Per-scene masthead (title + status + actions + tabs) | 73 |
| `PageHeading` | H1 block — 32px/medium, asymmetric vertical rhythm | 96 |
| `KpiCard` / `KpiGrid` | Editorial big-number cards (2/3/4/5 column) | 168 + 54 |
| `ExecutiveSummary` | Narrative hero block with LLM-stream skeleton | 138 |
| `SettingsSection` | Editable section (H2 + body + Edit action) | 95 |
| `OrderedList` | Numbered editorial list (read + editable modes) | 187 |
| `ThreePaneLayout` / `LogicCard` / `LiveSummaryPanel` | Editor shells | 59 / 91 / 101 |
| `Illustration` | Notioly SVGs themed via `currentColor` | 87 |
| `ChatPanel` (rewrite) | Glass AI bubble + 24px ink send button | 227 |
| `Tag` (2× rewrite) | Same-hue alpha-core + 5px dot + unified inset edge | 193 |

Storybook stories for every new pattern (Catalog · SizeLadder · Theming ·
InEmptyState · etc.).

### R14.4 — Sidebar architecture (Outset four-zone)

Replaced abstract "Workspace / Library" group labels with flat entity
navigation anchored top + user-identity anchored bottom:

| Zone | Component | Behaviour |
|---|---|---|
| 1 | `WorkspaceAnchor` | Team name + chevron (click → /settings) |
| 2 | Flat entity nav | Home · Studies · Ask · Inbox · Repository · Decisions |
| 3 | `PinnedStudies` | localStorage-backed max-3 recent + inline "New study" |
| 4 | `UserBadge` + Settings | Avatar + name + email + sign out |

`sidebarLogic.ts` uses a `touchStudy` listener on `sceneLogic.setScene` so
the current study auto-pins whenever the user navigates in.

### R14.5 — Home scene

New `Scene.Home` at `/` (was mapped to Ask) with:
- 5-column `KpiGrid`: Sessions · Studies · Talk time · Participants ·
  Insights, served by `GET /api/home/stats/`.
- Horizontal `StudyCard` strip + tail "+ Start a new study" card.
- `FirstStudyHero` illustration-backed empty state (`planning-a-trip`).
- Overview / Activity / Drafts sub-tabs (Overview implemented).

### R14.6 — Study settings scene + model change

- **Backend**: `Study.research_objectives: JSONField(default=list)` added —
  migration `0004_study_research_objectives` applied. North-Star
  `research_goal` kept single-line (AI anchor).
- **Frontend**: `/studies/:id/settings` — `SettingsSection` + `OrderedList`
  composition, per-section edit mode via `studySettingsLogic`.
- **Security fix**: `TeamScopedModelViewSet.perform_create` now always
  injects `team` when the model has `team_id` (was gated on serializer
  exposing the field). Closed the `POST /api/studies/` null-team path.

### R14.7 — Per-page sub-nav + illustration wiring

`PageTopBar` applied to all seven top-level pages:

| Page | Tabs (default bold) | Illustration (empty state) |
|---|---|---|
| Home | **Overview** · Activity · Drafts | `planning-a-trip` (xl) |
| Studies | **All** · Active · Drafts · Archived | `jumping` (xl) |
| Ask | **Chat** · History · Saved | `fast-internet` (md) |
| Inbox | **All** · Unread · Flagged | `chill-time` (xl) |
| Repository | **Documents** · Chunks · Templates | `painting` (xl) |
| Decisions | **Open** · Closed · Linked | `flag` (xl) |

Studies page filter tabs are real (client-side `visibleStudies` slicing).

### R14.8 — Header compaction (last pass)

- `PageHeading` title: 48px display → 32px headline · weight 450 → 500.
- Asymmetric rhythm: eyebrow→title 8px, title→lede 8px, lede→hairline 24px.
- Inline `status` slot baseline-aligned with title (replaces right-side tag).
- `AppLayout` top pad: 72 → 24. Top-level pages outer gap 64 → 32.
- Token `--spacing-merism-page-top` retained for future marketing heroes
  but no longer applied in app shell.

Net vertical-space reclaim: **~80px per scene** from TopBar edge to first
interactive element.

### Verification at final checkpoint

```
backend pytest : 59 passed + 1 skipped
frontend       : typecheck 0 · vitest 37 · oxlint 0 · vite build 3.6s
kea typegen    : 21 logics
storybook      : HMR live on :6006
API smoke     : GET /api/home/stats/ → 200 · POST /api/studies/ → 201
```

### R14.5 — Home scene

New `Scene.Home` at `/` (was mapped to Ask) with:
- 5-column `KpiGrid`: Sessions · Studies · Talk time · Participants ·
  Insights, served by `GET /api/home/stats/`.
- Horizontal `StudyCard` strip + tail "+ Start a new study" card.
- `FirstStudyHero` illustration-backed empty state (`planning-a-trip`).
- Overview / Activity / Drafts sub-tabs (Overview implemented).

### R14.6 — Study settings scene + model change

- **Backend**: `Study.research_objectives: JSONField(default=list)` added —
  migration `0004_study_research_objectives` applied. North-Star
  `research_goal` kept single-line (AI anchor).
- **Frontend**: `/studies/:id/settings` — `SettingsSection` + `OrderedList`
  composition, per-section edit mode via `studySettingsLogic`.
- **Security fix**: `TeamScopedModelViewSet.perform_create` now always
  injects `team` when model has `team_id` (was gated on serializer exposing
  the field). Closed the `POST /api/studies/` null-team path.

### R14.7 — Per-page sub-nav + illustration wiring

`PageTopBar` applied to all seven top-level pages:

| Page | Tabs (default bold) | Illustration (empty state) |
|---|---|---|
| Home | **Overview** · Activity · Drafts | `planning-a-trip` (xl) |
| Studies | **All** · Active · Drafts · Archived | `jumping` (xl) |
| Ask | **Chat** · History · Saved | `fast-internet` (md) |
| Inbox | **All** · Unread · Flagged | `chill-time` (xl) |
| Repository | **Documents** · Chunks · Templates | `painting` (xl) |
| Decisions | **Open** · Closed · Linked | `flag` (xl) |

Studies page filter tabs are real (client-side `visibleStudies` slicing).

### R14.8 — Header compaction (last pass)

- `PageHeading` title 48px display → 32px headline · weight 450 → 500.
- Asymmetric rhythm: eyebrow→title 8px, title→lede 8px, lede→hairline 24px.
- Inline `status` slot baseline-aligned with title (replaces right-side tag).
- `AppLayout` top pad 72 → 24. Top-level pages outer gap 64 → 32.
- Token `--spacing-merism-page-top` retained for future marketing heroes
  but no longer applied in app shell.

Net vertical-space reclaim: **~80px per scene** from TopBar edge to first
interactive element.

### Verification at final checkpoint

```
backend pytest : 59 passed + 1 skipped
frontend       : typecheck 0 · vitest 37 · oxlint 0 · vite build 3.6s
kea typegen    : 21 logics
storybook      : HMR live on :6006
API smoke      : GET /api/home/stats/ → 200 · POST /api/studies/ → 201
```

### R14.8 — Header compaction (last pass)

- Title 48 → 32px · weight 450 → 500.
- Asymmetric rhythm: eyebrow→title 8px, title→lede 8px, lede→hairline 24px.
- Inline `status` slot baseline-aligned with title.
- `AppLayout` top pad 72 → 24. Pages outer gap 64 → 32.
- Net reclaim: ~80px per scene.

### Verification at R14 close

```
backend pytest : 59 passed + 1 skipped
frontend       : typecheck 0 · vitest 37 · oxlint 0 · vite build 3.6s
kea typegen    : 21 logics
storybook      : HMR live on :6006
API smoke      : GET /api/home/stats/ → 200 · POST /api/studies/ → 201
```

## ✅ R15 — Runtime harness + end-to-end automation

Closes the gap between "link can be sent" and "link runs end-to-end
unattended". See [`docs/RUNTIME.md`](RUNTIME.md) for the full design
writeup. Eight tightly-scoped steps.

### R15.0 — SessionEvent event log

New `merism_session_event` table. Append-only, monotone `seq` per
session, atomic allocation via `select_for_update`. Service module
`merism/conductor/event_log.py`:

- `append_event(session, kind, payload, trace_id=...)`
- `append_events(session, iterable, trace_id=...)` — batched atomic
- `reconstruct_state(session) → ExecutionState` — fold events
- `current_transcript(session)` — project events to transcript shape

`moderator_state` / `transcript` / `decision_log` on the session row
are now **derived caches**. The events are authoritative, which is
how we get resumability after process restart.

Migration: `0009_sessionevent`.
Tests: `merism/conductor/tests/test_event_log.py` (9).

### R15.1 — trace_id vertical

`trace_id: UUIDField` added to:
- `Participation` (default uuid4)
- `DeliveryRecord` (nullable, stamped by adapter)
- `InterviewSession` (copied from participation on start)
- `SessionInsight` (copied from session)
- `SessionEvent` (carried from session on append)

New module `merism/observability.py::bind_trace` binds the id into
structlog `contextvars` for a block. Admin `Participation` list
exposes `trace_id_short` + a custom `/trail/` view that aggregates
DeliveryRecord + SessionEvent + SessionInsight into a chronological
timeline.

Migration: `0010_deliveryrecord_trace_id_interviewsession_trace_id_and_more`.
Tests: `merism/tests/test_trace_id_propagation.py` (4).

### R15.2 — Invitation + per-recipient token

PIPL/GDPR-grade closed-audience support. `StudyLink.require_invitation`
flag (default False — existing open-audience studies unchanged).
When True, `/i/<slug>/?t=<token>` requires a matching `Invitation`
row; otherwise a forwarded link works as before.

`recruitment.tasks._delivery_context` auto-creates an Invitation per
recipient, renders the participant URL with `?t=<token>`, and
propagates the Invitation's trace_id down to the Delivery row and
eventually to the Participation on first click.

Migration: `0011_studylink_require_invitation_invitation`.
Tests: `merism/participant/test_invitation_flow.py` (6).

### R15.3 — moderator → text pipeline + guardrails

- `POST /api/sessions/<id>/message/` — SSE stream of `delta` deltas
  and final `done` with decision. Cookie-authenticated
  (`merism_browser_token`).
- `stream_turn` writes `SessionEvent` rows per turn.
- `max_probes` hard cap enforced server-side even when the LLM
  disagrees (via existing `decision_validator`).
- Frontend: `TextInterviewPage` + `textInterviewLogic`;
  `InterviewRoomPage` dispatches to text when `?mode=text`;
  `ParticipantEntryPage` appends `?mode=text` when
  `study.interview_mode == "text"`.

Tests: `merism/conductor/tests/test_moderator_events.py` (2) +
`merism/api/tests/test_interview_message_view.py` (3).

### R15.4 — 6-signal closure + orphan cleanup

`merism/conductor/closure.py` with six closure signals (OR logic,
first match wins):

| # | Signal |
|---|---|
| A | moderator `next_action=close` |
| B | all P0 goals answered + elapsed ≥ min_duration |
| C | leaving-intent regex match |
| D | idle > 120s |
| E | WS disconnected > 30s AND ≥ 4 turns |
| F | elapsed ≥ max_duration |

Plus Celery beat `abandon_stuck_sessions` every 10 minutes for any
in-progress session > 2h. `complete_session` is atomic + idempotent
and sets both session and Participation to COMPLETED, emits a
`session_lifecycle=ended` event.

Migration: `0012_participation_completed_at`.
Tests: `merism/conductor/tests/test_closure.py` (7).

### R15.5 — Study counter aggregated

`Study.actual_completed_count` changed from stored counter (race-prone
`+= 1`) to a `@property` that runs `COUNT(*)` on the
Participation set. Admin/API use `Study.annotate_completed_count()`
to avoid N+1.

`study_closure_signal` auto-closes the Study (status=CLOSED +
matching StudyLinks.is_active=False) when target is reached. Preview
participations ignored. `_resolve_link` maps to the more-useful
`study_full` (409) instead of `link_closed` (410) when the link was
auto-closed due to quota.

Tests: `merism/tests/test_study_counter.py` (5).

### R15.6 — Researcher Inbox notifications

New `merism_inbox_item` table with
`unique_together=(team, kind, ref_kind, ref_id)` — dedup at the DB.
Three signal handlers in `conductor/inbox_signals.py` write items
for `session_completed`, `insight_ready`, `study_completed`.

Frontend `InboxPage` rewritten to load `/api/inbox-items/` and render
with `Mark read` action; empty state preserved via i18n keys.

Migration: `0013_inboxitem`.
Tests: `merism/tests/test_inbox_signals.py` (5).

### R15.7 — moderator → voice pipeline

`ModeratorLLMProcessor` (`merism/voice/processors/moderator.py`)
replaces the generic `LLMProcessor` whenever `session.guide_id`
is set. Wires every `TranscriptionFrame` into `stream_turn` and
streams the resulting content deltas as `LLMTextFrame`s to TTS.
`InterruptionFrame` flips a cancellation flag; the moderator
generator drains cleanly.

Voice tests updated to patch `stream_turn` alongside the existing
STT/TTS/LLM stubs.

### R15.8 — post_session Celery chain + broadcast catch-up

`process_completed_session` now launches a Celery `chain`:
- `stage_polish_transcript` — intelligent-verbatim cleanup
- `stage_extract_and_tag` — codebook + quotes + tags
- `stage_index_and_insight` — RAG index + SessionInsight

Each stage retries independently (3 × 30s); idempotent at the domain
level. `process_completed_session_inline` preserved for admin replay.

`dispatch_pending_broadcasts` periodic task (every 60s) re-enqueues
APPROVED/SENDING broadcasts whose initial `.delay()` may have been
lost (web dyno crash before task hit Redis).

### R15 — Verification at close

```
backend pytest : 211 passed + 1 skipped  (+57 vs R14 close)
frontend       : typecheck 0 · vitest 39 · oxlint 0 · vite build 2.30s
e2e smoke      : merism/tests/test_e2e_automation.py — 1 test walks
                 invite → consent → screener → moderator → closure →
                 auto-close → inbox in <6s with mocked LLM
migrations     : 0009 sessionevent · 0010 trace_id · 0011 invitation ·
                 0012 completed_at · 0013 inboxitem
```
