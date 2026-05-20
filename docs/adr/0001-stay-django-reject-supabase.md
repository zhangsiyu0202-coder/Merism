# ADR 0001 — Stay on Django; reject Supabase / BaaS

**Status:** Accepted (2026-05-10)
**Deciders:** Jia
**Supersedes:** nothing
**Superseded by:** nothing

## Context

Merism was rebuilt from scratch on Django 5.2 + Postgres + Redis + Celery in
May 2026 (see `docs/ROADMAP.md` R1-R11). The question has come up: should
we instead use Supabase, or a similar batteries-included BaaS, to
accelerate development?

## Decision

**Merism stays on Django.** Supabase (and any similar BaaS) is rejected as
the primary platform.

We adopt **six** specific accelerator libraries that capture Supabase's
best properties without ceding control:

| # | Library | Replaces |
|---|---|---|
| 1 | `django-allauth`    | Supabase Auth (JWT + magic link + OAuth + 2FA) |
| 2 | `django-unfold`     | Supabase Dashboard (Django Admin re-skin) |
| 3 | `django-anymail`    | Supabase email (deferred; add when needed) |
| 4 | `langfuse`          | no Supabase equivalent — LLM observability |
| 5 | `openapi-zod-client` (frontend) | PostgREST (auto-typed API client) |
| 6 | `django-procrastinate` | ❌ rejected — Celery + Redis stays |

## Rationale

### Why stay on Django

1. **Python AI ecosystem dominance.** Merism runs three agents
   (Outline Review / Interview Moderator / Analysis) making thousands of
   LLM calls per day. The Python AI stack (openai, pydantic-ai, langchain,
   instructor) is ~10× deeper than Deno/TypeScript. Edge Functions on
   Supabase would force every AI piece through a worse toolchain.
2. **Chinese-market fit.** Feishu / WeCom / QQ Group / QQ Guild / WeCom
   Bot all ship Python SDKs first. DashScope (Qwen / Paraformer /
   CosyVoice) runs in Alibaba Cloud with China-optimised routes; Supabase
   regions are `us-east-1` / `eu-central-1` with 200-400 ms RTT from
   mainland China and occasional censorship disruption.
3. **Sunk cost is asset.** R1-R11 delivered 91 backend files — settings,
   models with `merism_` prefix, 56 models (initial 27 grew to 56 by R26), IMChannel adapters, report
   schema, test harness. All of it works with Django conventions.
4. **Self-hosting.** Django + Postgres + Redis is trivial to self-host
   on a single VPS for MVP, or Kubernetes at scale. Self-hosted Supabase
   exists but is a 20-container compose with fragile upgrade paths.

### Why adopt the six accelerators

- **`django-allauth`** — Saves 2 weeks of hand-rolling auth. We need
  email/password, password reset, OAuth (Feishu/WeCom/Google), and 2FA.
  Mature, 12-year-old library.
- **`django-unfold`** — Django Admin has tremendous productivity for
  internal ops, but the default UI looks like 2010. Unfold is a
  Tailwind re-skin with sidebar, modals, dashboard widgets. One
  dependency, zero lock-in (uninstall = back to stock admin).
- **`django-anymail`** — When recruitment via email lands, swap provider
  (Mailgun → SES → Postmark → Resend) by changing env vars.
- **`langfuse`** (self-hosted, Apache 2.0) — Merism's moderator agent
  runs thousands of turns per day. Without per-call trace + cost
  attribution we're flying blind. Langfuse has a Python SDK that
  auto-instruments OpenAI-compatible calls via a single
  `@observe()` decorator. Self-hostable on the same Postgres instance.
- **`openapi-zod-client`** — DRF + drf-spectacular produce OpenAPI at
  build time. This tool turns that into typed fetch client + Zod
  schemas, eliminating hand-written API types in the frontend.

### Why reject the rest

| Rejected | Reason |
|---|---|
| Supabase (all-in) | Explained above |
| `django-ninja` (FastAPI-style) | DRF + drf-spectacular already delivers typed API + OpenAPI; switching mid-flight is invasive |
| `django-procrastinate` | Excellent single-worker, but Celery + Redis scale-out path is better trodden |
| Clerk / WorkOS / Auth0 | SaaS auth; China latency + data-sovereignty concerns; django-allauth does everything we need |
| LiteLLM proxy | Adds a hop; direct `openai.OpenAI(base_url=...)` switch already covers DeepSeek / OpenAI / Anthropic (via Anthropic-compat) |
| Temporal / Hatchet / Inngest | Workflow engines; Celery beat + behavior trigger scanner is already the ADR-0001 path |
| PostgREST | Loses permissions / throttle / serializer validation — DRF viewsets are not replaceable by auto-generated REST |
| Dagster / Prefect | Data pipeline orchestrators; not our shape |
| Next.js / Remix | Framework-ed frontend; SPA + Django decouples better at our scale |
| PostHog analytics (self-hosted) | Merism rebuilt specifically to shed PostHog — adding it back as a dep would be ironic |

## Consequences

### Positive

- No vendor lock-in; no migration risk.
- Full control of the AI stack — use any new Python LLM library the day it ships.
- Works offline / self-hosted in China without region gymnastics.
- Team already knows Django — zero training cost.

### Negative

- No native realtime-over-Postgres; we hand-build SSE and WS consumers.
  Mitigated by `merism.realtime` module design (see `merism/realtime/README.md`).
- No dashboard for Postgres rows out of the box; we rely on Django Admin
  (plus Postico / pgAdmin for raw SQL when needed).
- Auth flows that would take one line in Supabase (`signInWithMagicLink`)
  take 10 lines in django-allauth. Worth it for the control.

### Neutral

- Langfuse adds one more Postgres DB to operate (self-hosted variant).
  Optional — can run as SaaS first and self-host later if retention
  becomes a concern.

## Revisit conditions

This ADR should be re-opened if:

1. We need enterprise SSO (SAML / SCIM) in < 2 weeks and don't have
   engineering capacity — consider Clerk or WorkOS for auth only,
   keeping Django for everything else.
2. Moderator agent observability stops being a concern and Langfuse
   cost exceeds ~$200/mo — re-evaluate by switching to self-hosted.
3. Django's async story regresses badly. (Unlikely — 5.x async support
   is improving.)
