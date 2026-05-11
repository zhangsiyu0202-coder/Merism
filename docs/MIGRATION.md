# Migration map — where each module came from

Quick reference for tracing any `merism-app/` file back to its source in
the old `posthog-foss` cutover repo. Useful when comparing behavior or
hunting for a missing helper.

## Ported verbatim (no logic changes)

| merism-app/ | source in old repo |
|---|---|
| `merism/testing/` | `merism/testing/` (created in this session's Phase B.5) |
| `merism/recruitment/adapters/base.py` | `products/studies/backend/recruitment/channels/base.py` |
| `merism/recruitment/adapters/feishu_adapter.py` | `products/studies/backend/recruitment/channels/feishu_adapter.py` |
| `merism/recruitment/adapters/wecom_bot_adapter.py` | `products/studies/backend/recruitment/channels/wecom_bot_adapter.py` |
| `merism/recruitment/adapters/qq_group_adapter.py` | `products/studies/backend/recruitment/channels/qq_group_adapter.py` |
| `merism/recruitment/adapters/qq_guild_adapter.py` | `products/studies/backend/recruitment/channels/qq_guild_adapter.py` |
| `merism/recruitment/renderer.py` | `products/studies/backend/recruitment/renderer.py` |
| `merism/recruitment/rate_limit.py` | `products/studies/backend/recruitment/rate_limit.py` |
| `merism/recruitment/builtin_templates.py` | `products/studies/backend/recruitment/builtin_templates.py` |
| `docs/PRODUCT.md` | `standalone/PRODUCT.md` |
| `docs/specs/cowagent-im-recruitment/` | `.kiro/specs/cowagent-im-recruitment/` |
| `docs/specs/merism-design-system/` | `.kiro/specs/merism-design-system/` |
| `docs/specs/merism-platform/` | `.kiro/specs/merism-platform/` |

## Ported with minor rewrites

| merism-app/ | source in old repo | rewrite |
|---|---|---|
| `merism/recruitment/adapters/factory.py` | `products/studies/backend/recruitment/channels/factory.py` | Imports `merism.recruitment.adapters.*` instead of `products.studies.backend.recruitment.channels.*` |
| `merism/recruitment/crypto.py` | `products/studies/backend/recruitment/crypto.py` | Prefers `settings.MERISM_CHANNEL_ENCRYPTION_KEY` env var, falls back to PBKDF2-on-SECRET_KEY for dev convenience |

## Written from scratch (reference spec — not old repo)

| merism-app/ | reference |
|---|---|
| `pyproject.toml` | Old repo had one huge `pyproject.toml` for a 50-product monorepo. This one lists only what Merism itself uses. |
| `merism/settings/{base,dev,test,prod}.py` | Old repo's `posthog/settings/` sprawled across 20+ files. This is a clean four-file split. |
| `merism/urls.py` | Old `posthog/urls.py` had ~100 route groups. This is ~8 lines + per-domain includes. |
| `merism/apps.py` | Single-app project; no sub-app fragmentation. |
| `merism/models/team.py` | Native `merism.Team`. Old repo used `posthog.Team` for everything — we deliberately do NOT. |
| `merism/models/study.py` | Follows platform spec Req 1-10. Old repo had both `Study.research_goal` field AND a `StudyGoal` multi-goal flat list; spec Req 21.3/21.4 says drop the flat list, so we did. |
| `merism/models/interview.py` | Follows platform spec Req 4/9-15. New `Participation.is_preview` column (Req 8). `InterviewSession.audio_s3_key` kept as empty by convention (Req 12.4 — voice mode never persists audio). |
| `merism/models/knowledge.py` | L1 / L2 KB split per spec Req 19. `pgvector.django.VectorField` imported with sqlite JSONField fallback so tests run on sqlite. |
| `merism/models/recruitment.py` | Per IM-recruitment spec Req 1-5. `credentials_encrypted` is a binary blob, never plaintext. `ChannelHealthCheck` is new (append-only probe log). |
| `merism/models/report.py` | Per platform spec Req 16-19. `StudyReport.blocks` JSONField validated by the Pydantic v2 schema at `merism/reports/schema.py` (R7). |
| `merism/models/memory.py` | MEM AI state. Scoped to `merism.Team` (not `posthog.Team`). |
| `merism/tests/test_boundary.py` | New boundary enforcement. Asserts zero `posthog.*` loaded. |
| `bin/setup-dev.sh` | Written fresh. Old repo had many flox-specific scripts — this has no flox dep. |
| `docker-compose.yml` | Strip old repo's ClickHouse / Kafka / Temporal services. |

## Deliberately NOT ported (per spec)

These existed in the old repo but the spec says drop them:

| NOT ported | why |
|---|---|
| `merism/conductor/macro.py` (LangGraph 3-layer graph) | Platform spec Req 14.7 — moderator is a **single LLM call**, not macro/meso/micro |
| `products/studies/backend/conductor/policies/` (coverage_steer, engagement, off_topic) | Platform spec Req 21.5 — defer policies until 100+ real interviews inform the design |
| `merism/memai/tools/{execute_sql, create_insight, upsert_dashboard, call_mcp_server, create_form, create_notebook, list_data, read_data, read_data_warehouse_schema, read_taxonomy, search}.py` | None are Merism features — these are PostHog-product-specific tools |
| `merism/memai/core/agent_modes/presets/{product_analytics, session_replay, error_tracking, flags, survey, llm_analytics, sql}.py` | All map 1:1 to PostHog products |
| `merism/memai/chat_agent/rag/nodes.py` | Depends on `posthog.hogql_queries` — will be replaced with a Merism-native retrieval node in R8 |
| `merism/memai/chat_agent/memory/nodes.py` (PostHog taxonomy onboarding) | The onboarding questions were "what events do you track?" — Merism's equivalent is "what research are you running?", which is a different flow |
| `merism/memai/chat_agent/slash_commands/commands/usage/` | Queries PostHog billing — Merism has its own usage model |
| `merism/memai/insights_assistant.py` | Generates PostHog Insight (Trends/Funnels/Retention) — Merism has no Insight concept |
| `posthog/*`, `ee/*`, `products/{alerts,analytics_platform,batch_exports,cdp,...}` | 50+ PostHog-origin products — not Merism's scope |
| `plugin-server/` | ADR 0001 — behavior triggers run in Celery beat, not Node plugin server |
| `.flox/` | Downgraded to optional in old repo's Phase A; not needed in new repo at all |
| `posthog/test/base.py` and 51 tests that import from it | Replaced by `merism.testing` (Phase B.5) |

## Deliberate deviations from PRODUCT.md §6

PRODUCT.md was written while the old `posthog-foss` cutover was still the
target repo, so some lines reference PostHog-internal abstractions that we
can't preserve in the clean-slate `merism-app/`. Deviations:

| PRODUCT.md says | merism-app does | Why |
|---|---|---|
| "对象存储: PostHog object_storage (S3 抽象)" | `boto3` against S3 / MinIO directly, configured via `OBJECT_STORAGE_*` env vars | PostHog's `object_storage` module depends on its Django app graph. Rolling our own thin wrapper is a few dozen lines; keeping a PostHog dep just for storage is not worth it. |
| "所有 LLM 调用通过 `posthoganalytics.ai.openai` 包装" | `openai.OpenAI` with DeepSeek `base_url`; optional `posthoganalytics` Python SDK (pypi package — **not** the `posthog.*` Django app) can be added as a trace/cost instrumentation wrapper in `merism.memai.llm` without violating the no-PostHog rule. | `posthoganalytics` the SDK is a separate, pip-installable package. If cost tracking is a hard requirement we add it; otherwise defer. |

## Shape fix (applied 2026-05-10)

`StudyReport.blocks` → `StudyReport.content` + `StudyReport.charts`. The
earlier `blocks` flat-list representation didn't match PRODUCT.md §4 or
`merism-platform` Req 17. The lower-level block schema (text/metric/quote/
chart blocks) still exists — it's now the format of things INSIDE each
panel of `content`, validated by `merism.reports.schema` (R7).



## If you need a file that's not here

Check the "NOT ported" list above first — if it's there, there's a spec
reason not to carry it over.

If it's not there, and you genuinely need it, grep the old repo:
```bash
cd /home/jia/posthog-foss     # old repo
rg --files | grep <keyword>
```
and add a corresponding row to this table when you port it.

## R15 runtime harness additions (2026-05-11)

Entirely new to Merism — no old-repo provenance. See
`docs/RUNTIME.md` for the architecture writeup.

| File | Role | Migration |
|---|---|---|
| `merism/models/session_event.py` | Append-only turn log | `0009_sessionevent` |
| `merism/models/invitation.py` | Per-recipient token + trace_id | `0011_studylink_require_invitation_invitation` |
| `merism/models/inbox.py` | Researcher-facing notifications | `0013_inboxitem` |
| `merism/conductor/event_log.py` | Append / replay service | — |
| `merism/conductor/closure.py` | 6-signal closure + orphan cleanup | — |
| `merism/conductor/study_closure_signal.py` | Auto-close on target reached | — |
| `merism/conductor/inbox_signals.py` | InboxItem post_save writers | — |
| `merism/observability.py` | `bind_trace` structlog context manager | — |
| `merism/api/interview_message_view.py` | Text-mode SSE turn endpoint | — |
| `merism/voice/processors/moderator.py` | `ModeratorLLMProcessor` (replaces `LLMProcessor` when guide present) | — |
| `frontend/src/features/interview/TextInterviewPage.tsx` + logic | Text-mode participant UI | — |
| `frontend/src/features/inbox/*` | Inbox page + logic | — |
| `merism/participant/views.py` | Invitation-aware resolve; preview bypass; auto-close disambiguation | — |
| `merism/recruitment/tasks.py` | `_delivery_context` creates Invitation + stamps trace_id; `dispatch_pending_broadcasts` catch-up | — |

Field additions (non-model files):

| Table | New column | Migration |
|---|---|---|
| `merism_participation` | `trace_id: UUIDField(default=uuid4, indexed)` | `0010_*` |
| `merism_participation` | `completed_at: DateTimeField(null)` | `0012_*` |
| `merism_interview_session` | `trace_id: UUIDField(null, indexed)` | `0010_*` |
| `merism_delivery_record` | `trace_id: UUIDField(null, indexed)` | `0010_*` |
| `merism_session_insight` | `trace_id: UUIDField(null, indexed)` | `0010_*` |
| `merism_study_link` | `require_invitation: BooleanField(default=False)` | `0011_*` |
