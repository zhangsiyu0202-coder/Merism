# Merism frontend

**React 19 · Vite 6 · TypeScript 5.7 · Tailwind v4 · Kea 3 · Radix · Motion · ECharts.**

Designed for: 简约但不简单 · 张扬但不高调 · 克制的放大.

## Stack — and why each piece is here

| Layer | Choice | Why not X |
|---|---|---|
| Bundler | Vite 6 | Next/Remix would impose a framework; we stay SPA + Django |
| CSS | **Tailwind v4** | 5× compile speed, native `@theme`, no postcss config |
| State | **Kea 3** (+ kea-router / -subscriptions / -waitfor / -loaders) | Rule in AGENTS.md: no `useState/useEffect` for business logic |
| Primitives | **Radix** + our own copy-in-repo components | Owning the code means zero lib-drift risk (shadcn pattern) |
| Animation | **Motion v12** | Smallest API for spring-based "克制的放大"; Framer Motion is 40% bigger |
| Icons | **lucide-react** | 1500+ icons, tree-shakes to single-icon bundles |
| Command palette | **cmdk** | Same author as Sonner/Vaul; minimalist, accessible |
| Toasts | **Sonner** | No theme fight with dark mode; 20-line integration |
| Charts | **echarts-for-react** | PRODUCT.md §3.6 specifies ECharts; chart.js too weak for report panels |
| Validation | **Zod 3** | Mirrors the Pydantic backend; codegen-compatible |
| Testing | **Vitest 3 · RTL · user-event · MSW 2 · Playwright** | Industry standard 2026 stack |
| Storybook | **Storybook 9 + addon-vitest** | Stories double as Vitest tests — no duplicate effort |
| Lint/format | **oxlint + Prettier** | Rust-speed, zero config drift |

## Quick start

```bash
pnpm install
pnpm dev                # http://localhost:5173 — proxies /api + /admin to Django on :8000
```

## Structure

```
frontend/
├── package.json
├── vite.config.ts              # prod + dev server (Tailwind v4 plugin)
├── vitest.config.ts            # tests — kept separate from Vite for Storybook integration
├── playwright.config.ts        # E2E
├── tsconfig.json
├── index.html
├── e2e/                        # Playwright specs
│   └── smoke.spec.ts
└── src/
    ├── main.tsx                # bootstraps React + Sonner Toaster
    ├── globals.css             # Tailwind v4 entry + theme imports + motion prefs
    ├── app/
    │   └── AppShell.tsx        # app chrome + top-level surface routing
    ├── ask/                    # Ask Merism surface (LIVE)
    │   ├── AskMerism.tsx
    │   ├── askMerismLogic.ts   # Kea logic — owns conversation + SSE streaming
    │   ├── askMerismLogic.test.ts
    │   ├── types.ts
    │   ├── CitationStrip.tsx   # inline [1] [2] citations with Plex Mono lazy-load
    │   └── ChartRenderer.tsx   # ECharts wrapper — bar/line/pie
    ├── interview_room/         # TODO — participant voice/video room
    ├── wizard/                 # TODO — study creation wizard
    ├── inbox/                  # TODO
    ├── repository/             # TODO
    ├── assistant/              # AI assistant surface
    ├── design_system/
    │   ├── tokens/
    │   │   ├── variables.css   # :root / html.dark CSS var bridge
    │   │   └── theme.css       # Tailwind v4 @theme — all merism-* utilities
    │   ├── primitives/         # 8 primitives per spec Req 2 — all with tests
    │   ├── patterns/           # PageShell · TabBar · ChatPanel · StudyCard · SessionRow
    │   ├── fonts/
    │   │   ├── fonts.css       # Inter + Geist eager
    │   │   └── preload.ts      # loadPlexMono() lazy + memoised
    │   ├── lib/cn.ts           # twMerge + clsx helper
    │   └── index.ts            # single public entrypoint
    └── test/
        ├── setup.ts            # vitest + MSW lifecycle
        ├── render.tsx          # custom render() with TooltipProvider + Kea resetContext
        ├── fixtures.ts         # makeStudy / makeCitation / makeChartSpec
        └── msw/
            ├── server.ts
            ├── handlers.ts
            └── index.ts
```

## Commands

| Command | What |
|---|---|
| `pnpm dev` | Vite dev server, HMR, `/api` proxy |
| `pnpm build` | tsc strict check + Vite build (rejects > 250 KB chunks) |
| `pnpm typecheck` | `tsc --noEmit` |
| `pnpm lint` · `pnpm lint:fix` | oxlint |
| `pnpm format` · `pnpm format:check` | Prettier + prettier-plugin-tailwindcss |
| `pnpm test` | Vitest unit (jsdom + MSW) |
| `pnpm test:watch` | Vitest watch mode |
| `pnpm test:coverage` | v8 coverage; fails under 80% lines/functions/statements |
| `pnpm test:e2e` · `pnpm test:e2e:ui` | Playwright; auto-starts Django + Vite after clearing stale `8000` / `5173` listeners |
| `pnpm storybook` · `pnpm storybook:build` | Storybook 9 |

## Conventions — enforced

1. **Never** import LemonUI. **Never** use slate-\* or hex literals in
   business code. Only `merism-*` utilities + primitives + patterns from
   `~/design_system`.
2. **Never** use `useState` / `useEffect` for business logic. Kea logic
   files own data + state. `useState` is for ephemeral UI only (a single
   disclosure flag, a hover highlight).
3. **Named exports only.** No `export default`.
4. **File name = main export name.** `AppShell.tsx`, `askMerismLogic.ts`,
   never `index.tsx`.
5. Tests: **prefer** `~/test/render` over `@testing-library/react` directly,
   **prefer** factories in `~/test/fixtures` over literal objects.
6. Motion: use `motion/react` + `cubic-bezier(0.22, 0.61, 0.36, 1)` via
   `--ease-merism`. No linear easings. No > 350ms durations in app code.
7. Charts: import via `~/ask/ChartRenderer` — don't touch ECharts directly
   from app code.

## What's built (live)

- ✅ 8 primitives (Button / Card / Input / Tag / StatusDot / Tooltip /
  Dialog / Tabs) with full unit tests per spec Req 5
- ✅ 5 patterns (PageShell / TabBar / ChatPanel / StudyCard / SessionRow)
- ✅ Test scaffold (custom render, MSW, fixtures, Vitest 3 with coverage)
- ✅ Playwright smoke test
- ✅ **Ask Merism** — full surface with SSE streaming, citations, charts
- ✅ **Interview Room** — 3-phase flow (mode select → mic check → live
  room) with:
  - Silero VAD (ONNX, via `@ricky0123/vad-web`) — see
    `src/interview_room/voice/SileroVad.ts`
  - AudioWorklet-backed mic capture with 300 ms pre-speech ring buffer
    and silence suppression — see `src/interview_room/voice/AudioCapture.ts`
  - Shared-AudioContext playback with barge-in interrupt — see
    `src/interview_room/voice/AudioPlayback.ts`
  - Pre-session mic check with real-time level meter +
    text-mode fallback — see `src/interview_room/voice/MicCheck.tsx`
- ✅ AppShell routing between Ask + Interview + Surface catalog

## Voice architecture (ADR 0002 + 0003)

End-to-end latency budget under 1.2 s typical:

```
user speaks
  → Silero VAD onSpeechStart (client, <90 ms)
  → AudioCapture flushes 300 ms pre-pad buffer to WS
  → Paraformer streaming STT (server)
  → moderator.stream_turn 2-node pipeline: coverage_steer (decide) → generate (stream) (server)
    → text delta → WS → CaptionColumn + CosyVoice TTS
  → AudioPlayback on shared AudioContext (<20 ms decode)
AI speaks
  ↳ if study.barge_in_enabled AND Silero onSpeechStart fires again
    → server cancels TTS/moderator task
    → `barge_in_accepted` → AudioPlayback.interrupt()
    → participant's voice takes over immediately
```

## What's pending

See `docs/ROADMAP.md` § R9 follow-up:

- Interview Room (voice/video participant surface — biggest remaining piece)
- Study Wizard (create + outline + screener + stimuli)
- Inbox / Repository / Assistant surfaces
- Kea router wiring
- API client codegen from DRF spec (drf-spectacular → Zod schemas)
- Storybook story files for every primitive + pattern
- Visual-regression tests via Chromatic / Storybook test-runner
