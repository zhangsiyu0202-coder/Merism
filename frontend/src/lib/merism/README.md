# `~/lib/merism` — Merism design system

The single entry point for every piece of UI in the Merism frontend.

```
import {
    Button, Card, Tag,                  // primitives
    PageTopBar, KpiGrid, KpiCard,       // patterns
    SettingsSection, OrderedList,
    Illustration,                       // illustrations
    cn, loadPlexMono,                   // utilities
} from "~/lib/merism"
```

**Rules (enforced by convention + lint):**

- No LemonUI, no raw Tailwind `slate-*` / `red-*` utilities, no hex literals.
- Every colour goes through a `--merism-*` token.
- Every spacing is a multiple of 4 (strict 8pt grid; sub-grid 4 allowed for micro).
- Every radius picks from the 7-tier radius ladder.
- Every animation uses `cubic-bezier(0.22, 0.61, 0.36, 1)` via `--merism-ease`.

## Layers

```
tokens       CSS vars + Tailwind @theme bridge
  ↓
primitives   atomic building blocks
  ↓
patterns     composed shells + editorial pieces
  ↓
illustrations SVG assets themed via currentColor
  ↓
surfaces     feature scenes (Home / Studies / Ask / Inbox / …)
```

## Tokens

See `tokens/variables.css` + `tokens/theme.css`.

### Colours (Slate neutrals + Coral accent)

| Token                | Light                       | Dark                   |
| -------------------- | --------------------------- | ---------------------- |
| `merism-bg`          | `#F9FAFB`                   | `#0F172A`              |
| `merism-surface`     | `#FFFFFF`                   | slate-800              |
| `merism-bg-subtle`   | slate-100                   | slate-700              |
| `merism-text`        | `#0F172A`                   | slate-50               |
| `merism-text-muted`  | `#64748B`                   | slate-400              |
| `merism-text-subtle` | `#94A3B8`                   | slate-500              |
| `merism-border`      | `#E2E8F0`                   | rgba(255,255,255,0.08) |
| `merism-hairline`    | rgba(15,23,42,0.06)         | rgba(255,255,255,0.08) |
| `merism-accent`      | `oklch(0.69 0.17 28)` Coral | `oklch(0.74 0.16 30)`  |
| `merism-accent-soft` | core / 10% alpha            | core / 16% alpha       |

### Typography scale (strict 8pt)

| Token                  | Size          | Line-height | Tracking |
| ---------------------- | ------------- | ----------- | -------- |
| `text-merism-hero`     | 72            | 1.05        | -0.02em  |
| `text-merism-display`  | 48            | 1.05        | -0.02em  |
| `text-merism-headline` | 32            | 1.15        | -0.02em  |
| `text-merism-h2`       | 24            | 1.2         | -0.015em |
| `text-merism-title`    | 20            | 1.3         | -0.01em  |
| `text-merism-subtitle` | 18            | 1.35        | -0.005em |
| `text-merism-body`     | 16            | 1.5         | 0        |
| `text-merism-body-sm`  | 14            | 1.5         | 0        |
| `text-merism-label`    | 13            | 1.4         | 0        |
| `text-merism-caption`  | 12            | 1.35        | +0.02em  |
| `text-merism-mono`     | 13 Geist Mono | 1.3         | 0        |

### Radii · Spacing · Elevation · Motion

- **Radii**: `xs 4 · sm 6 · md 8 · lg 12 · xl 16 · 2xl 24 · full 9999`.
- **Spacing**: all multiples of 4 (sub-grid 2 only for micro borders).
- **Shadows**: `xs · sm · card · float · pop` (diffuse rgba(15,23,42,α)).
- **Tracking utilities**: `caps` (0.14em) · `caps-tight` (0.12em) · `tight` (-0.005em) · `display` (-0.02em).
- **Motion**: `--merism-ease` + `--merism-duration-{fast|base|slow}` (120/200/300ms).
- **Status palette**: `--merism-status-{neutral|accent|success|warning|danger|info}` core + matching `-bg` at 8-9% alpha + unified `-edge` 1px inset shadow.
- **Scrollbar**: `--merism-scrollbar-thumb` (10% alpha idle) + `-hover` (25%).

## Primitives

| Component            | Purpose                                                                                                             |
| -------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `Button`             | primary / secondary / ghost / danger / link · sm 32 / md 40 / lg 48 / icon 40                                       |
| `Card` + parts       | Hairline-ring + shadow-card surface (no solid border)                                                               |
| `Input` / `Textarea` | Form field with hairline-strong edge · aria-invalid                                                                 |
| `Tag`                | Same-hue alpha-core chip · 5px dot · unified inset edge · 7 variants × 3 sizes × 2 case                             |
| `StatusDot`          | ok / warn / error / neutral (+ pulse) · required label                                                              |
| `Tooltip`            | Radix wrapper · Provider at app root                                                                                |
| `Dialog`             | Focus trap + Escape close + `dismissible=false`                                                                     |
| `Tabs`               | Radix wrapper · underline style · keyboard nav                                                                      |
| `Select`             | Custom trigger + floating listbox · 44px touch target · soft hover · accent-soft selected state · fade/slide motion |

## Patterns

| Component             | Role                                                           |
| --------------------- | -------------------------------------------------------------- |
| `PageTopBar`          | Per-scene masthead (eyebrow + title + status + actions + tabs) |
| `PageHeading`         | H1 block with asymmetric 8/8/24 rhythm                         |
| `KpiCard` / `KpiGrid` | Big-number cards (borderless or card variant) · 2/3/4/5 cols   |
| `ExecutiveSummary`    | Narrative hero with LLM-stream skeleton                        |
| `SettingsSection`     | Editable section (H2 + body + Edit affordance)                 |
| `OrderedList`         | Numbered 1.2.3. list — read + edit modes                       |
| `LogicCard`           | Numbered editor unit (Outline / Screener / Stimuli)            |
| `LiveSummaryPanel`    | Right-column stats panel with crossfade                        |
| `ThreePaneLayout`     | `left / main / right` responsive grid                          |
| `ChatPanel`           | Glass AI bubbles + immersive input + 24px ink send             |
| `StudyCard`           | Home/Studies list card                                         |
| `SessionRow`          | Inbox / Sessions table row                                     |
| `Sidebar`             | Legacy sidebar pattern                                         |
| `TabBar` / `TabRail`  | Active tab with Coral underline                                |
| `PageShell`           | Plain chrome for standalone pages                              |
| `SectionLabel`        | Mono uppercase section heading                                 |

## Illustrations

`Illustration` primitive loads 8 monochrome Notioly SVGs via `?raw` import.
Each SVG's `#231f20` was rewritten to `currentColor` at build time so tone
follows any `text-*` class on the wrapper.

| Name                     | Use                                |
| ------------------------ | ---------------------------------- |
| `planning-a-trip`        | Home FirstStudyHero                |
| `jumping`                | Studies empty hero                 |
| `fast-internet`          | Ask chat empty state               |
| `chill-time`             | Inbox empty state                  |
| `painting`               | Repository empty state             |
| `flag`                   | Decisions empty state              |
| `peace` · `loading-time` | Reserved (404 / loader candidates) |

Sizes: `sm 96 · md 128 · lg 192 · xl 256 · 2xl 320`.

## Utilities

- `cn(...classes)` — `clsx` + `tailwind-merge`.
- `loadPlexMono()` — idempotent dynamic import of IBM Plex Mono.

## Storybook catalogue

Every primitive + pattern has a `.stories.tsx`. Survey stories:

- `illustrations/Illustration/Catalog` — all 8 at a glance.
- `primitives/Tag/AllVariants` — alpha-core palette.
- `patterns/KpiCard/DashboardRow` — 4-column KPI row.
- `patterns/SettingsSection/FullSettingsPage` — full archetype.
- `patterns/ChatPanel/Default` — glass bubbles + immersive input.
- `patterns/PageTopBar/Full` — eyebrow + title + tabs + actions.

Run `pnpm storybook` locally on port 6006.

## Open TODOs

- `primitives/Select` — refactor off raw slate classes.
- `bin/align_8pt.py` — consider pre-commit hook.
- `ThreePaneLayout` + `LiveSummaryPanel` Storybook stories.
- ADR documenting the alpha-core Tag algorithm + Outset sidebar.
- `AudioPlayback.getPlayedMs()` jsdom tests.
