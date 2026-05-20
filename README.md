# Merism

**AI-moderated qualitative research platform.** Researchers write a research
goal, AI drafts the interview guide and reviews it, CowAgent IM channels
recruit participants, AI hosts the interview over voice/video, AI analyses
each session and generates a cited report, and multiple studies compound into
a queryable research knowledge base.

Built fresh in 2026-05. Zero PostHog lineage.

> **Status**: Skeleton phase. This repo replaces the old `posthog-foss` cutover
> approach with a clean Merism-native build. See [`docs/ROADMAP.md`](docs/ROADMAP.md)
> for what's implemented vs scaffolded.

## Quick start

```bash
# Prerequisites:
#   - Python 3.12.12
#   - Node.js 24.13.x (frontend only)
#   - Docker (for postgres + redis)
#   - uv (Python package manager)

bin/setup-dev.sh
```

This runs:
1. `docker compose up -d` (postgres + redis)
2. `uv sync` (install Python deps to `.venv/`)
3. `python manage.py migrate`
4. `python manage.py runserver`

Tests: `pytest merism/tests`

## Repo layout

```
merism-app/
├── merism/                         # Single Django project
│   ├── settings/                   # base / dev / test / prod
│   ├── urls.py
│   ├── models/                     # Team, Study, Interview, Knowledge, Recruitment, Report
│   ├── api/                        # DRF viewsets
│   ├── memai/                      # AI tool layer (Merism-native; not PostHog's hogai)
│   ├── conductor/                  # 2-node interview moderator: decide → generate (per platform spec)
│   ├── knowledge/                  # RAG (pgvector + BM25), Ask Merism
│   ├── recruitment/                # IMChannel adapters (Feishu, WeCom, QQ Group/Guild, WeCom Bot)
│   ├── realtime/                   # SSE + WebSocket (interview replay + voice)
│   ├── reports/                    # Block schema (text/metric/quote/chart)
│   ├── stt.py / tts.py / vision.py # AI adapters (Paraformer, CosyVoice, Qwen-VL)
│   └── testing/                    # Merism-native test harness (factories, fakes, assertions)
├── frontend/                       # React + Vite + TS + Kea
│   └── src/
│       ├── design_system/          # tokens / primitives / patterns
│       ├── app/                    # routing + auth shell
│       ├── ask/                    # Ask Merism
│       ├── interview_room/         # Participant-facing voice/video room
│       ├── wizard/                 # Study creation wizard
│       ├── inbox/                  # Recruitment + session inbox
│       ├── repository/             # Knowledge repository
│       └── decisions/              # Decision log
├── docs/
│   ├── PRODUCT.md                  # Single product spec
│   ├── ROADMAP.md                  # What's done, what's next
│   ├── MIGRATION.md                # Where each module came from
│   └── specs/                      # .kiro-style requirements + design + tasks
│       ├── merism-platform/
│       ├── merism-design-system/
│       └── cowagent-im-recruitment/
├── bin/setup-dev.sh
├── docker-compose.yml
├── pyproject.toml
├── pytest.ini
├── manage.py
├── AGENTS.md
└── README.md
```

## Testing

Three pytest entrypoints, all Merism-native (no `posthog.test.base`):

```bash
# Smoke / unit (no DB — fastest)
pytest merism/tests

# Single test
pytest merism/tests/test_boundary.py::test_no_posthog_in_sys_modules
```

See [`merism/testing/README.md`](merism/testing/README.md) for the harness
docs: factories, fakes, assertions, fixtures.

## Architecture principles

1. **Single Django project.** Not a monorepo of "products". Everything Merism
   does lives under `merism/`.
2. **Two-node interview moderator (decide → generate).** Each user turn
   runs `coverage_steer` (non-streaming, returns structured
   `ModeratorDecision`) → `decision_validator` (server-side hard rules)
   → `generate` (streaming text). Both calls live in one
   `stream_turn` coroutine. No macro/meso/micro pyramid, no persistent
   conductor policies (see spec `merism-platform` Req 14).
3. **`merism_` db_table prefix.** Every model. Always. Multi-tenant isolation
   via `team_id` on every tenant-data model.
4. **Research goal is the North Star.** `Study.research_goal: TextField`.
   Every AI step (guide generation / review / moderator / analysis / report /
   custom Q&A / knowledge base) anchors on this one field.
5. **DeepSeek + Qwen stack.** DeepSeek v3 (chat) / DeepSeek Reasoner
   (analysis) / Qwen CosyVoice (TTS streaming) / Qwen Paraformer (STT) /
   Qwen-VL-Max (vision).
6. **No ClickHouse, no HogQL, no Kafka.** Postgres + pgvector for everything
   data-heavy. Redis for queues and SSE. That's it.
7. **No plugin-server.** Behavior triggers run in Celery beat (per ADR 0001
   in the old repo).

## Preserved features (ported from the old cutover repo)

- **IMChannel recruitment**: Feishu, WeCom (both webhook bot and native app),
  QQ Group, QQ Guild adapters with encrypted credentials, message templates
  with placeholder rendering, broadcast dispatch, delivery tracking, health
  monitoring.
- **Merism design system**: Tokens (colors, typography, spacing, shadows,
  radii, breakpoints), primitives (Button/Card/Input/Tag/StatusDot/Tooltip/
  Dialog/Tabs), patterns (PageShell/TabBar/StudyCard/SessionRow/ChatPanel).
- **Merism platform**: Study CRUD, outline editor + AI review, screener,
  stimuli, recruitment, preview mode, consent + screener flow, voice/video
  interview room, 2-node moderator (decide → generate), session analysis,
  study report, custom report sidebar, cross-study knowledge explore.

See [`docs/MIGRATION.md`](docs/MIGRATION.md) for file-level provenance.

## What's NOT ported (deliberately dropped)

- Conductor 3-layer pyramid (macro / meso / micro split) — platform spec
  Req 14.7 forbids it; the 2-node moderator (decide → generate) does
  not split into more than two sequential LLM calls per turn.
- Conductor policies (coverage_steer / engagement / off_topic) — platform
  spec Req 21.5 defers persistent policy modules until 100+ real
  interviews inform the design. Coverage / engagement context is
  injected into the decision prompt, not stored in dedicated tables.
- MEM AI PostHog-product tools (execute_sql / create_insight / upsert_dashboard
  / session_replay / error_tracking / flags / surveys / llm_analytics) —
  none are Merism features.
- PostHog event/person data model and ClickHouse — Merism doesn't need them.
- Flox environment manager — plain `uv sync` is enough.

## Contributing

This is a proprietary, closed-source project. External contributions are not
accepted. Internal contributors should read [`CONTRIBUTING.md`](CONTRIBUTING.md)
and [`AGENTS.md`](AGENTS.md) before opening a pull request. For security
issues, follow the disclosure process in [`SECURITY.md`](SECURITY.md).

Standard checks before every PR:
- Python: `ruff check . --fix && ruff format .` and `pyright merism`
- TS: `pnpm --filter merism-frontend lint`
- Tests: always add a corresponding test in `merism/tests/` or the colocated
  `test_*.py` for new code.

## License

**Proprietary — All Rights Reserved.** This repository is closed-source and
is not open for public contribution, redistribution, or use outside the
Company's authorized internal teams and licensees. See [LICENSE](LICENSE)
for the full terms.

Unauthorized copying, modification, reverse-engineering, or disclosure of
any part of this Software is prohibited. For licensing inquiries, contact
[legal@merism.ai](mailto:legal@merism.ai).
