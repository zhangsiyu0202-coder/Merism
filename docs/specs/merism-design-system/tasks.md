# Implementation Tasks

Legend: `[x]` done before this spec · `[ ]` to do · `[-]` deferred

## Task 1: Tokens layer
- [x] 1.1 `tokens/colors.ts` (slate, functional, semantic, semanticDark)
- [x] 1.2 `tokens/typography.ts` (fontFamily, fontSize, lineHeight, fontWeight, letterSpacing, typePreset)
- [x] 1.3 `tokens/spacing.ts` (spacing, space)
- [x] 1.4 `tokens/shadows.ts` (3 tiers)
- [x] 1.5 `tokens/radii.ts` (3 tiers + full)
- [x] 1.6 `tokens/variables.css` (light + dark --m-* vars)
- [ ] 1.7 **`tokens/breakpoints.ts`** (sm/md/lg/xl/2xl matching Tailwind defaults)
- [ ] 1.8 **`tokens/index.ts`** add `export * from './breakpoints'`

**Depends on:** nothing
**Refs:** Requirement 1, Design §3

## Task 2: Tailwind config bridge
- [x] 2.1 `common/tailwind/tailwind.config.js` extended with `merism-*` namespace (colors, fontFamily, fontSize, spacing, boxShadow, borderRadius, transition)
- [x] 2.2 CSS variables imported via `frontend/src/styles/global.scss`

**Depends on:** Task 1
**Refs:** Requirement 1 AC 6

## Task 3: Primitive components
- [x] 3.1 Button (variant × size × loading + iconLeft/iconRight + asChild)
- [x] 3.2 Card + CardHeader + CardTitle + CardDescription + CardFooter
- [x] 3.3 Input + Textarea + InputLabel + InputHelperText + InputErrorText
- [x] 3.4 Tag (tone × size, removable)
- [x] 3.5 StatusDot (status × size × pulse)
- [x] 3.6 Tooltip (Radix wrapper)
- [x] 3.7 Dialog (Radix wrapper, size × dismissible)
- [x] 3.8 Tabs (Radix wrapper, underline style)
- [ ] 3.9 **Select primitive** — rewrite with merism-* tokens (currently uses raw slate-*)

**Depends on:** Task 1, Task 2
**Refs:** Requirement 2

## Task 4: Pattern components
- [x] 4.1 PageShell (sidebar + optional header + main, hover-expand sidebar)
- [ ] 4.2 **TabBar / PageHeaderTabs** (breadcrumb + title + statusDot + actions + tabs row + body)
- [x] 4.3 StudyCard (280×220 fixed)
- [x] 4.4 SessionRow (participant + quote + flags + actions)
- [x] 4.5 ChatPanel (optional filter rail + message column + input + optional suggestion rail)

**Depends on:** Task 3
**Refs:** Requirement 3

## Task 5: Canvas shell
- [x] 5.1 InterviewCanvasShell (parchment bg + recording badge + mic waveform + end button)
- [x] 5.2 TranscriptStream (question header + editorial turn list + streaming cursor)

**Depends on:** Task 3
**Refs:** Design §2

## Task 6: Font pipeline
- [ ] 6.1 **Install `@fontsource-variable/inter`, `@fontsource-variable/geist`, `@fontsource/ibm-plex-mono`** (exact pinned minor)
- [ ] 6.2 **Rewrite `fonts/fonts.css`** to `@import` Inter + Geist wght.css from @fontsource-variable; omit Plex Mono
- [ ] 6.3 **Implement `loadPlexMono()`** with memoised dynamic imports of `@fontsource/ibm-plex-mono/400.css` + `/500.css`
- [-] 6.4 HTML `<link rel="preload">` tags — deferred; the Django template layer is out of this sprint's remit. @fontsource packages ship fonts with `font-display: swap` and browser preload headers via the built CSS.
- [-] 6.5 Font metrics `size-adjust` / `ascent-override` fallback tuning — deferred; @fontsource variable fonts already include metric hints.

**Depends on:** nothing
**Refs:** Requirement 4

## Task 7: Storybook surface
- [x] 7.1 `tokens/Tokens.stories.tsx` (Colors, Typography, Spacing, Shadows, Radii)
- [x] 7.2 One `.stories.tsx` per primitive (8 files)
- [x] 7.3 One `.stories.tsx` per pattern (4 present — add TabBar.stories in Task 4.2)
- [x] 7.4 One `.stories.tsx` per canvas component (2 files)
- [x] 7.5 Storybook `addon-a11y` enabled globally in `common/storybook/.storybook/main.ts`
- [x] 7.6 Short MDX docs for each primitive

**Depends on:** Task 3, Task 4, Task 5
**Refs:** Requirement 3 AC 4

## Task 8: Tests
- [x] 8.1 Minimum test file per primitive
- [ ] 8.2 **Expand Button tests**: aria-disabled, aria-busy, asChild renders as anchor
- [ ] 8.3 **Expand Input tests**: invalid applies danger border class
- [ ] 8.4 **Expand Dialog / Tabs tests**: keyboard close and keyboard tab switching

**Depends on:** Task 3
**Refs:** Requirement 5

## Task 9: Documentation
- [x] 9.1 `fonts/README.md` explains the deferral (to be refreshed when Task 6 lands)
- [ ] 9.2 **`frontend/src/lib/merism/README.md`** — promote to full usage doc (tokens list, primitives list, patterns list, import pattern, Storybook pointer, DoD summary)
- [ ] 9.3 **Repo-root `AGENTS.md`** — add one-line rule: new Merism frontend imports from `~/lib/merism`

**Depends on:** Task 1–6
**Refs:** Requirement 6

## Task 10: Verification
- [ ] 10.1 `pnpm --filter=merism-frontend typescript:check` clean
- [ ] 10.2 `hogli test frontend/src/lib/merism` or equivalent jest run passes
- [ ] 10.3 `ruff check . --fix && ruff format .` no Python changes expected
- [ ] 10.4 Storybook story files compile (build-time discovery smoke check)

**Depends on:** all above
**Refs:** Requirement 7

## Deferred / explicitly not in scope
- Chromatic / Percy visual regression (Sprint 0.5 §10.2)
- size-limit / bundlewatch wiring (Sprint 0.5 §10.4) — add a budget note in README only
- Dark-mode primitive QA pass
- White-label runtime brand switch
- Migration of existing `products/studies/frontend/`
