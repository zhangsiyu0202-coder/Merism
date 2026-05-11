# Design Document — Merism Design System Foundation

> Full technical design is captured in the Sprint 0.5 plan delivered in-chat. This document
> summarises the architecture and records the concrete deltas required to reach the DoD.

## 1. Architecture — 3 layers, no cross-layer peeking

```
patterns  (PageShell · TabBar · StudyCard · SessionRow · ChatPanel)
   ↓ consumes
primitives (Button · Card · Input · Tag · StatusDot · Tooltip · Dialog · Tabs)
   ↓ consumes
tokens    (colors · typography · spacing · shadows · radii · breakpoints)
```

- Tokens never import from primitives. Primitives never import from patterns.
- Patterns MAY compose primitives + tokens. Canvas shells live in `canvas/`.
- Utilities live in `utils/` (`cn()` = `twMerge(clsx(…))`).

## 2. Directory layout (post-spec)

```
frontend/src/lib/merism/
├── tokens/
│   ├── colors.ts
│   ├── typography.ts
│   ├── spacing.ts
│   ├── shadows.ts
│   ├── radii.ts
│   ├── breakpoints.ts         ← ADDED by this spec
│   ├── variables.css
│   ├── Tokens.stories.tsx
│   └── index.ts               ← UPDATED to re-export breakpoints
├── primitives/
│   ├── Button, Card, Input, Tag, StatusDot, Tooltip, Dialog, Tabs (*.tsx + *.stories + *.test + *.mdx)
│   ├── Select.tsx             ← REFACTORED to merism-* tokens
│   └── index.ts
├── patterns/
│   ├── PageShell.tsx
│   ├── TabBar.tsx             ← ADDED by this spec (aka PageHeaderTabs)
│   ├── StudyCard.tsx
│   ├── SessionRow.tsx
│   ├── ChatPanel.tsx
│   ├── *.stories.tsx (incl. TabBar.stories.tsx)
│   └── index.ts
├── canvas/
│   ├── InterviewCanvasShell.tsx
│   ├── TranscriptStream.tsx
│   └── index.ts
├── fonts/
│   ├── fonts.css              ← REPLACED with @fontsource-variable imports
│   ├── preload.ts             ← REPLACED with real dynamic import
│   └── README.md
├── utils/
│   ├── cn.ts
│   └── index.ts
├── README.md                  ← EXPANDED usage table
└── index.ts
```

## 3. Tokens: breakpoints

New file `tokens/breakpoints.ts`:

```ts
/** Responsive breakpoints. Matches Tailwind default scale. */
export const breakpoints = {
    sm: 640,
    md: 768,
    lg: 1024,
    xl: 1280,
    '2xl': 1536,
} as const

export type Breakpoint = keyof typeof breakpoints
```

`tokens/index.ts` gets a new `export * from './breakpoints'` line.

## 4. Pattern: TabBar (PageHeaderTabs)

New file `patterns/TabBar.tsx`. Composes the Tabs primitive plus a page header skeleton.
Contract:

```ts
export interface PageHeaderTabsProps {
    breadcrumb?: React.ReactNode
    title: string
    statusDot?: React.ReactNode
    actions?: React.ReactNode
    tabs: Array<{ value: string; label: string }>
    activeTab: string
    onTabChange: (value: string) => void
    children: React.ReactNode
    className?: string
}
```

Layout:
- top row: breadcrumb (text-xs muted) · title (h2 preset) · statusDot inline · actions on the right
- tab row: TabsList with one TabsTrigger per `tabs[]`
- body: TabsContent per tab; consumer supplies via `children` (each child should have a `value` prop that matches a tab value). We keep implementation simple by rendering `children` inside the active TabsContent only when the consumer uses our recommended pattern; for now the component is a declarative wrapper.

We expose both the default export name `TabBar` and the alias `PageHeaderTabs` to match the Sprint 0.5 naming discussion.

## 5. Font pipeline

Before: `fonts.css` hand-declares Inter `@font-face` pointing to `public/Inter.woff2`; Plex Mono stub
returns immediately; `@fontsource-*` packages absent.

After:
- `pnpm --filter=@posthog/frontend add @fontsource-variable/inter@5.2.5 @fontsource-variable/geist@5.2.5 @fontsource/ibm-plex-mono@5.2.5` (pinned exact minor).
- `fonts/fonts.css` becomes:

```css
@import '@fontsource-variable/inter/wght.css';
@import '@fontsource-variable/geist/wght.css';
/* IBM Plex Mono is lazy-loaded via loadPlexMono(); do not import here. */
```

- `fonts/preload.ts`:

```ts
let pending: Promise<void> | null = null

export async function loadPlexMono(): Promise<void> {
    if (!pending) {
        pending = Promise.all([
            import('@fontsource/ibm-plex-mono/400.css'),
            import('@fontsource/ibm-plex-mono/500.css'),
        ]).then(() => undefined)
    }
    return pending
}
```

The memoised promise prevents duplicate network fetches if multiple Ask surfaces call `loadPlexMono()`.

## 6. Select primitive cleanup

`primitives/Select.tsx` today hardcodes `bg-white`, `border-slate-200`, `text-slate-700`, etc. That
violates the "primitives only consume merism tokens" rule. Two options:

- **Option A (selected)**: rewrite class strings to use `bg-merism-card`, `border-merism-border-subtle`, `text-merism-text`, `focus:ring-merism-border-focus`, etc. Keep the component signature unchanged so any existing call sites continue to compile.
- Option B (rejected): drop from barrel. Rejected because Sprint 0.5 explicitly lists Select as a useful primitive for wizard forms.

## 7. Test matrix

New or expanded cases per primitive:

| Primitive | Minimum cases |
|---|---|
| Button | renders text · variant class · ref forwarding · disabled sets `aria-disabled` · loading sets `aria-busy` · `asChild` renders as `<a>` |
| Card | renders composition · `interactive` toggles cursor class |
| Input | textbox role · label association · `invalid` applies danger border · forwards ref |
| Tag | renders content · removable button calls `onRemove` · accessible name |
| StatusDot | accessible label · status class applied |
| Tooltip | shows content on hover (existing) |
| Dialog | dialog visible · close button calls `onOpenChange(false)` |
| Tabs | tab switch via click changes panel content |

## 8. Documentation deltas

- `frontend/src/lib/merism/README.md` becomes a full usage doc: 3-layer diagram, import examples,
  token cheatsheet, Storybook pointer, DoD status.
- Repo-root `AGENTS.md` gains one rule line under the "Merism-specific architecture rules" section:
  *"All new Merism frontend (Ask / Interview / Wizard / Inbox / Repository / Decisions) imports
  primitives, patterns, and tokens from `~/lib/merism`. Do not introduce LemonUI components in new
  Merism surfaces."*

## 9. Out of scope

- Chromatic / Percy visual regression
- Dark-mode primitive QA pass (variables are in place; classes still need `dark:` prefixes next sprint)
- White-label runtime brand switch (variables slot `[data-merism-brand]` is prepared but not wired)
- size-limit CI wiring (Sprint 0.5 §10.4 left as a follow-up; we add a manual budget note in README)
- Migration of existing `products/studies/frontend/` files
