# Requirements Document

## Introduction

Sprint 0.5 为 Merism 前端建立设计系统基座,确保后续 Ask / Interview Room / Wizard / Inbox / Repository / Assistant 等 sprint 直接消费 tokens / primitives / patterns,而不重复决策"按钮长什么样"。

本 spec 在 Sprint 0.5 技术设计已大部分落地后,把剩余未完成项(breakpoints token、TabBar pattern、fontsource 自托管、Plex Mono 懒加载、字体预加载、测试覆盖、size-limit、Select 清理、AGENTS.md 指引)补齐,并把整份 Sprint 0.5 工件形式化为可追溯的 spec。

不在范围内:整套 Ask / Interview / Wizard UI;LemonUI 迁移;完整 dark mode 视觉实现;白标 runtime 切换;新增业务逻辑。

## Glossary

- **Token**: TypeScript 常量 + CSS 变量 + Tailwind 主题扩展三位一体的设计原子(颜色、字号、间距、阴影、圆角、断点)
- **Primitive**: 基于 Radix UI 的原子组件(Button、Card、Input、Tag、Tooltip、StatusDot、Dialog、Tabs)
- **Pattern**: 组合多个 primitive 解决页面级布局问题的组件(PageShell、TabBar、StudyCard、SessionRow、ChatPanel)
- **Canvas shell**: Interview Room 专用的全屏外壳,羊皮纸背景 + 底部录音控制条
- **Merism namespace**: Tailwind 里以 `merism-` 前缀命名的 token / class,与 LemonUI 并存不冲突
- **CSS variable bridge**: `:root` / `html.dark` 下定义的 `--m-*` 变量,由 Tailwind 的 `rgb(var(--m-*) / <alpha-value>)` 桥接
- **Font preload**: HTML `<link rel="preload">` 标签,让关键字体在首次渲染前已到达
- **Lazy font**: 初始 bundle 不含的字体(IBM Plex Mono),仅在需要的页面(Ask citations)动态 import

## Requirements

### Requirement 1: Tokens 层完整性

**User Story:** As a Merism 前端工程师, I want 所有后续 sprint 都能从 `~/lib/merism/tokens` 拿到完整的设计原子, so that 我不必在业务组件里硬编码颜色、字号、间距、断点等数值。

#### Acceptance Criteria

1. THE tokens module SHALL export `slate`, `functional`, `semantic`, `semanticDark`, `fontFamily`, `fontSize`, `lineHeight`, `fontWeight`, `letterSpacing`, `typePreset`, `spacing`, `space`, `shadows`, `radii`, `breakpoints` as readonly const objects.
2. THE `tokens/breakpoints.ts` file SHALL define `sm=640`, `md=768`, `lg=1024`, `xl=1280`, `2xl=1536` pixel values matching Tailwind defaults.
3. THE `tokens/index.ts` barrel SHALL re-export every token module including `breakpoints`.
4. WHEN TypeScript compiles, THE tokens module SHALL expose `SemanticColorToken`, `TypePresetKey`, `ShadowToken`, `RadiusToken` union types.
5. THE `tokens/variables.css` file SHALL define `--m-*` CSS variables for bg, text, border, accent, state, and quote under both `:root` and `html.dark` selectors.
6. THE Tailwind config at `common/tailwind/tailwind.config.js` SHALL expose `merism-*` color / font / spacing / shadow / radius / transition utilities derived from the token modules.

### Requirement 2: Primitive 组件完整且一致

**User Story:** As a Merism 前端工程师, I want 8 个 primitive 组件 (Button, Card, Input, Tag, StatusDot, Tooltip, Dialog, Tabs) 都以 merism-* tokens 实现, so that 样式一致、可访问、可测试。

#### Acceptance Criteria

1. THE primitives barrel at `frontend/src/lib/merism/primitives/index.ts` SHALL re-export Button, Card (+ CardHeader/CardTitle/CardDescription/CardFooter), Input (+ Textarea/InputLabel/InputHelperText/InputErrorText), Tag, StatusDot, Tooltip, Dialog, Tabs (+ TabsList/TabsTrigger/TabsContent).
2. EVERY primitive SHALL reference only `merism-*` Tailwind utilities or CSS variables — no raw `slate-*`, `bg-white`, or literal hex values.
3. Button SHALL support `variant` ∈ {primary, secondary, ghost, danger}, `size` ∈ {sm, md, lg}, `loading`, `iconLeft`, `iconRight`, `asChild`.
4. Button SHALL expose `aria-disabled` when disabled or loading, and `aria-busy` when loading.
5. Tag SHALL support `removable` and call `onRemove` when the remove button is clicked; the remove button SHALL have an accessible name.
6. Dialog SHALL trap focus, close on Escape when `dismissible=true`, and stay open on Escape when `dismissible=false`.
7. Tabs SHALL support keyboard navigation (ArrowLeft / ArrowRight / Home / End) via Radix defaults.
8. THE Select primitive (if kept) SHALL use merism-* tokens; otherwise it SHALL be removed from the barrel.

### Requirement 3: Pattern 组件 5 个齐全

**User Story:** As a Merism 前端工程师, I want 5 个 pattern 组件覆盖常见页面骨架 (PageShell, TabBar, StudyCard, SessionRow, ChatPanel), so that 页面搭建只是把 pattern 组装起来。

#### Acceptance Criteria

1. THE patterns barrel SHALL re-export PageShell, TabBar (PageHeaderTabs), StudyCard, SessionRow, ChatPanel.
2. TabBar SHALL accept `breadcrumb`, `title`, `statusDot`, `actions`, `tabs`, `activeTab`, `onTabChange`, `children` and render a page header with a tab row underneath.
3. TabBar SHALL use the Tabs primitive internally.
4. EVERY pattern SHALL have a `.stories.tsx` file under `frontend/src/lib/merism/patterns/` or `frontend/src/lib/merism/canvas/`.

### Requirement 4: 字体自托管与延迟加载

**User Story:** As a Merism 用户, I want 关键字体(Inter、Geist)在首次渲染前已到达,而 IBM Plex Mono 只在进入 Ask 页面时按需加载, so that 初始 FCP 不退化且 citation 字体出现时不闪烁。

#### Acceptance Criteria

1. THE frontend package SHALL depend on `@fontsource-variable/inter`, `@fontsource-variable/geist`, and `@fontsource/ibm-plex-mono` with pinned minor versions.
2. THE `fonts/fonts.css` file SHALL `@import` the Inter and Geist variable weight CSS from @fontsource-variable and SHALL NOT import Plex Mono.
3. THE `fonts/preload.ts` module SHALL export `loadPlexMono()` that dynamically imports `@fontsource/ibm-plex-mono/400.css` and `@fontsource/ibm-plex-mono/500.css`.
4. THE `loadPlexMono()` function SHALL memoise the import so repeated calls do not re-trigger network requests.

### Requirement 5: 测试覆盖最小矩阵

**User Story:** As a maintainer, I want each primitive 覆盖 variant / state / a11y 关键路径的单元测试, so that 回归问题能在 jest 层捕捉。

#### Acceptance Criteria

1. Button.test.tsx SHALL assert (a) rendered text, (b) variant class application, (c) ref forwarding, (d) `aria-disabled` and `aria-busy` when loading, (e) `asChild` renders as anchor.
2. Input.test.tsx SHALL assert (a) textbox role, (b) label association, (c) invalid state class application.
3. Tag.test.tsx SHALL assert removable button invokes `onRemove` and has an accessible name.
4. Dialog.test.tsx SHALL assert dialog visible when open and close button calls `onOpenChange(false)`.
5. Tabs.test.tsx SHALL assert tab switching via pointer click changes panel content.
6. EVERY test file SHALL import from the adjacent source and use `@testing-library/react`.

### Requirement 6: 导入约定与 AGENTS.md 同步

**User Story:** As a Merism maintainer, I want AGENTS.md 明文要求新 Merism 前端从 `~/lib/merism` 导入, so that 贡献者不会把新代码接到 LemonUI 上。

#### Acceptance Criteria

1. THE repo-root `AGENTS.md` SHALL contain a rule stating that all new Merism frontend code must import primitives / patterns / tokens from `~/lib/merism`.
2. THE `frontend/src/lib/merism/README.md` SHALL document the import entry point, the 3-layer architecture (tokens → primitives → patterns), and point to Storybook for visual reference.

### Requirement 7: Verification gates

**User Story:** As a reviewer, I want a single script or checklist to confirm the DoD items from Sprint 0.5 §13 all pass, so that merging S0.5 is defensible.

#### Acceptance Criteria

1. `pnpm --filter=merism-frontend typescript:check` SHALL pass with no new errors introduced by this spec.
2. `hogli test frontend/src/lib/merism` (or equivalent jest invocation) SHALL pass for every `.test.tsx` under `lib/merism/`.
3. `ruff check . --fix && ruff format .` SHALL report no changes for touched Python files (there should be none).
4. THE Storybook dev or build invocation SHALL discover every new `.stories.tsx` and render without console errors.
